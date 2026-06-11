import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from src.importer import DinnerImporter
from src.optimizer import DinnerOptimizer
from src.validator import validate_plan
from src.mailer import write_emails
from src.map_generator import generate_team_maps
from src.aggregated_map_generator import generate_aggregated_map

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def _make_run_id(requested_run_id: str | None) -> str:
    if requested_run_id:
        return requested_run_id
    return datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')

def _prepare_run_dir(output_root: Path, run_id: str) -> Path:
    run_dir = output_root / 'runs' / run_id
    if run_dir.exists():
        existing_names = {path.name for path in run_dir.iterdir()}
        if existing_names.issubset({'manifest.json', 'pipeline.log'}):
            return run_dir
        suffix = 2
        while (output_root / 'runs' / f'{run_id}-{suffix}').exists():
            suffix += 1
        run_dir = output_root / 'runs' / f'{run_id}-{suffix}'
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir

def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

def _relative_to_output(path: Path, output_root: Path) -> str:
    return str(path.relative_to(output_root))

def _write_run_index(output_root: Path, manifest: dict):
    runs_dir = output_root / 'runs'
    index_path = runs_dir / 'index.json'
    if index_path.exists():
        with index_path.open('r', encoding='utf-8') as f:
            index = json.load(f)
    else:
        index = {'runs': []}

    summary = {
        'run_id': manifest['run_id'],
        'created_at': manifest['created_at'],
        'status': manifest['status'],
        'input': manifest['input'],
        'event': manifest.get('event', {}),
        'stats': manifest.get('stats', {}),
        'validation': manifest.get('validation', {}),
        'artifacts': manifest.get('artifacts', {}),
    }

    index['runs'] = [r for r in index.get('runs', []) if r.get('run_id') != manifest['run_id']]
    index['runs'].insert(0, summary)
    _write_json(index_path, index)
    _write_json(runs_dir / 'latest.json', summary)
    (runs_dir / 'latest.txt').write_text(manifest['run_id'] + '\n', encoding='utf-8')

def _write_plan_json(path: Path, plan):
    matches = [
        {
            'course': match.course.value,
            'host_id': match.host_id,
            'guest_ids': match.guest_ids,
        }
        for match in plan.matches
    ]
    _write_json(path, {'matches': matches, 'total_distance': plan.total_distance, 'is_valid': plan.is_valid})

def _build_event_info(args) -> dict:
    return {
        'title': args.event_title or 'Running Dinner',
        'date': args.event_date or '',
        'time': args.event_time or '',
        'meeting_point': args.event_meeting_point or '',
        'meeting_point_en': args.event_meeting_point_en or '',
        'additional_info': args.event_info or '',
        'additional_info_en': args.event_info_en or '',
    }

def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Running Dinner Pipeline")
    parser.add_argument('--input', required=True, help="Path to LimeSurvey JSON export")
    parser.add_argument('--output', default='data/output', help="Output root directory")
    parser.add_argument('--db', default='data/intermediate/dinner.db', help="Path to SQLite DB for cache")
    parser.add_argument('--trials', type=int, default=1000, help="Number of optimization trials")
    parser.add_argument('--run-id', help="Optional stable ID for this run")
    parser.add_argument(
        '--include-remainder-teams',
        action='store_true',
        help="Include teams even if the team count is not divisible by 3; some course groups may then be smaller or larger.",
    )
    parser.add_argument('--event-title', default='Running Dinner', help="Event title for generated emails")
    parser.add_argument('--event-date', default='', help="Event date for generated emails")
    parser.add_argument('--event-time', default='', help="Event start time for generated emails")
    parser.add_argument('--event-meeting-point', default='', help="Meeting/final location information for generated emails")
    parser.add_argument('--event-meeting-point-en', default='', help="English meeting/final location information for generated emails")
    parser.add_argument('--event-info', default='', help="Additional event information for generated emails")
    parser.add_argument('--event-info-en', default='', help="English additional event information for generated emails")
    
    args = parser.parse_args()
    input_path = Path(args.input)
    output_root = Path(args.output)
    run_dir = _prepare_run_dir(output_root, _make_run_id(args.run_id))
    run_id = run_dir.name
    event_info = _build_event_info(args)

    manifest = {
        'run_id': run_id,
        'created_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'status': 'running',
        'input': {
            'path': str(input_path),
            'sha256': _file_sha256(input_path) if input_path.exists() else None,
        },
        'parameters': {
            'trials': args.trials,
            'db': args.db,
            'include_remainder_teams': args.include_remainder_teams,
        },
        'event': event_info,
        'artifacts': {
            'run_dir': _relative_to_output(run_dir, output_root),
        },
    }
    _write_json(run_dir / 'manifest.json', manifest)
    _write_run_index(output_root, manifest)

    logger.info(f"Run ID: {run_id}")
    logger.info(f"Run directory: {run_dir}")
    
    # 1. Import
    logger.info("Step 1: Importing Data")
    importer = DinnerImporter(args.input, args.db)
    teams = importer.import_teams()
    manifest['stats'] = {'imported_teams': len(teams)}
    
    if len(teams) < 3:
        logger.error("Not enough teams to proceed (minimum 3).")
        manifest['status'] = 'failed'
        manifest['error'] = 'Not enough teams to proceed (minimum 3).'
        _write_json(run_dir / 'manifest.json', manifest)
        _write_run_index(output_root, manifest)
        return

    # 2. Optimization
    logger.info("Step 2: Optimizing Plan")
    optimizer = DinnerOptimizer(teams, include_remainder_teams=args.include_remainder_teams)
    plan = optimizer.optimize(n_trials=args.trials)
    active_ids = {t.id for t in optimizer.active_teams}
    active_teams = optimizer.active_teams
    inactive_teams = [t for t in teams if t.id not in active_ids]
    inactive_ids = [t.id for t in inactive_teams]
    manifest['stats'].update({
        'active_teams': len(active_ids),
        'inactive_teams': len(inactive_ids),
        'inactive_team_ids': inactive_ids,
        'inactive_team_names': [t.team_name for t in inactive_teams],
    })
    
    if not plan.is_valid:
        logger.error("Failed to generate a valid plan!")
        manifest['status'] = 'failed'
        manifest['error'] = 'Failed to generate a valid plan.'
        _write_json(run_dir / 'manifest.json', manifest)
        _write_run_index(output_root, manifest)
        return
        
    logger.info(f"Plan generated with total distance: {plan.total_distance:.2f} km")

    # 3. Validation
    logger.info("Step 3: Validating Plan")
    valid, errors = validate_plan(plan, active_ids, optimizer.address_conflicts)
    manifest['stats']['total_distance'] = round(plan.total_distance, 2)
    manifest['stats']['same_address_conflicts'] = len(optimizer.address_conflicts)
    manifest['validation'] = {
        'valid': valid,
        'errors': errors,
    }
    
    if valid:
        logger.info("Validation Successful! ✅")
    else:
        logger.error("Validation Failed! ❌")
        for e in errors:
            logger.error(f" - {e}")
        # Proceeding anyway? Maybe not.
        logger.warning("Proceeding to generate artifacts despite validation errors (for inspection).")

    # 4. Export Artifacts
    logger.info(f"Step 4: Generating Artifacts in {run_dir}")
    email_dir = run_dir / 'emails'
    map_dir = run_dir / 'maps'
    aggregated_map_path = run_dir / 'aggregated_map.html'
    plan_path = run_dir / 'plan.json'
    email_cnt = write_emails(plan, active_teams, str(email_dir), event_info)
    logger.info(f"Generated {email_cnt} email files.")
    
    generate_team_maps(plan, active_teams, str(map_dir))
    generate_aggregated_map(plan, active_teams, str(aggregated_map_path))
    _write_plan_json(plan_path, plan)

    manifest['status'] = 'completed' if valid else 'completed_with_validation_errors'
    manifest['artifacts'].update({
        'manifest': _relative_to_output(run_dir / 'manifest.json', output_root),
        'plan': _relative_to_output(plan_path, output_root),
        'emails_dir': _relative_to_output(email_dir, output_root),
        'maps_dir': _relative_to_output(map_dir, output_root),
        'aggregated_map': _relative_to_output(aggregated_map_path, output_root),
    })
    manifest['stats']['email_files'] = email_cnt
    _write_json(run_dir / 'manifest.json', manifest)
    _write_run_index(output_root, manifest)

    logger.info("Pipeline Complete.")

if __name__ == "__main__":
    main()
