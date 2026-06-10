from typing import List, Tuple, Set, Optional
from collections import defaultdict
from .models import DinnerPlan, CourseType

def validate_plan(
    plan: DinnerPlan,
    all_team_ids: Set[int],
    address_conflicts: Optional[Set[Tuple[int, int]]] = None,
) -> Tuple[bool, List[str]]:
    errors = []
    
    host_counts = defaultdict(int)
    guest_counts = defaultdict(int)
    meetings = defaultdict(set) # team_id -> set of met team_ids
    
    # Check coverage
    teams_in_plan = set()
    
    for match in plan.matches:
        host_id = match.host_id
        teams_in_plan.add(host_id)
        host_counts[host_id] += 1
        
        # Track meetings for host
        for guest_id in match.guest_ids:
            meetings[host_id].add(guest_id)
            meetings[guest_id].add(host_id)
            
            # Guest-Guest meetings
            for other_guest in match.guest_ids:
                if guest_id != other_guest:
                    meetings[guest_id].add(other_guest)

        for guest_id in match.guest_ids:
            teams_in_plan.add(guest_id)
            guest_counts[guest_id] += 1
            
    # Rule 1: All teams involved
    missing = all_team_ids - teams_in_plan
    if missing:
        errors.append(f"Teams missing from plan: {missing}")
        
    for tid in all_team_ids:
        # Rule 2: Host exactly once
        if host_counts[tid] != 1:
            errors.append(f"Team {tid} hosts {host_counts[tid]} times (expected 1).")
            
        # Rule 3: Guest exactly twice
        if guest_counts[tid] != 2:
            errors.append(f"Team {tid} is guest {guest_counts[tid]} times (expected 2).")
            
    # Rule 4: No repeat meetings (Soft constraint in optimization, fast validation here)
    # Actually optimization enforces it strictly.
    # Note: If A met B, they shouldn't meet again.
    
    # My simple validator above just aggregated meetings.
    # To check repeats correctly, we need to correct the loop logic.
    # Currently `meetings` set automatically dedupes, so I can't count.
    
    # Re-scan for repeats
    meeting_counts = defaultdict(int)
    for match in plan.matches:
        # Host meets all guests
        for gid in match.guest_ids:
            pair = tuple(sorted((match.host_id, gid)))
            meeting_counts[pair] += 1
            
        # Guests meet each other
        for i in range(len(match.guest_ids)):
            for j in range(i+1, len(match.guest_ids)):
                pair = tuple(sorted((match.guest_ids[i], match.guest_ids[j])))
                meeting_counts[pair] += 1
                
    for pair, count in meeting_counts.items():
        if count > 1:
            errors.append(f"Teams {pair[0]} and {pair[1]} meet {count} times.")

    address_conflicts = address_conflicts or set()
    for pair in sorted(address_conflicts):
        if meeting_counts.get(pair, 0) > 0:
            errors.append(f"Teams {pair[0]} and {pair[1]} share an address and meet in the plan.")

    return len(errors) == 0, errors
