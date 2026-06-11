import math
import random
import optuna
import logging
import re
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
import itertools

from .models import Team, DinnerPlan, MatchResult, CourseType

logger = logging.getLogger(__name__)

class DinnerOptimizer:
    def __init__(
        self,
        teams: List[Team],
        end_coordinates: Tuple[float, float] = (48.400199, 11.720124),
        include_remainder_teams: bool = False,
    ):
        self.teams = teams
        self.end_lat, self.end_lon = end_coordinates
        self.distance_matrix = {}
        self.distance_to_end = {}
        self.include_remainder_teams = include_remainder_teams
        
        self.active_teams = self._get_active_teams()
        self.address_conflicts = self._build_address_conflicts()

    def _get_active_teams(self) -> List[Team]:
        if len(self.teams) < 3:
            raise ValueError("Need at least 3 teams for a running dinner")

        if self.include_remainder_teams:
            if len(self.teams) % 3:
                logger.info(
                    "Including remainder teams with uneven dinner group sizes "
                    f"({len(self.teams)} teams total)."
                )
            return self.teams
        
        limit = (len(self.teams) // 3) * 3
        if limit < len(self.teams):
            logger.warning(f"Dropping {len(self.teams) - limit} teams to ensure divisibility by 3")
        return self.teams[:limit]

    def _normalize_address_key(self, team: Team) -> str:
        raw = f"{team.address_street} {team.address_zip} {team.address_city}"
        return re.sub(r"\s+", " ", raw.lower()).strip()

    def _build_address_conflicts(self) -> Set[Tuple[int, int]]:
        by_address = defaultdict(list)
        for team in self.active_teams:
            by_address[self._normalize_address_key(team)].append(team.id)

        conflicts = set()
        for team_ids in by_address.values():
            if len(team_ids) < 2:
                continue
            for id1, id2 in itertools.combinations(team_ids, 2):
                conflicts.add(tuple(sorted((id1, id2))))

        if conflicts:
            logger.info(f"Detected {len(conflicts)} same-address team conflict(s).")
        return conflicts

    def _teams_may_meet(self, id1: int, id2: int, existing_meetings: Set[Tuple[int, int]], strict: bool) -> bool:
        pair = tuple(sorted((id1, id2)))
        if pair in self.address_conflicts:
            return False
        if strict and pair in existing_meetings:
            return False
        return True

    def _calculate_haversine(self, lat1, lon1, lat2, lon2):
        R = 6371  # km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) * math.sin(dlon / 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def build_distance_matrix(self):
        logger.info("Building distance matrix...")
        for i, t1 in enumerate(self.active_teams):
            # To end
            self.distance_to_end[t1.id] = self._calculate_haversine(t1.latitude, t1.longitude, self.end_lat, self.end_lon) * 4
            
            for t2 in self.active_teams:
                if t1.id == t2.id:
                    continue
                dist = self._calculate_haversine(t1.latitude, t1.longitude, t2.latitude, t2.longitude)
                self.distance_matrix[(t1.id, t2.id)] = dist

    def _find_valid_guest_assignment(self, hosts: List[int], potential_guests: List[int], 
                                     existing_meetings: Set[Tuple[int, int]], 
                                     trial: optuna.Trial, course: str) -> Tuple[Optional[Dict[int, List[int]]], int]:
        # Try strict first
        result = self._attempt_assignment(hosts, potential_guests, existing_meetings, trial, course, strict=True)
        if result:
            return result, 0
            
        # If strict fails, try relaxed (allow repeats)
        # We can penalize based on number of repeats
        result = self._attempt_assignment(hosts, potential_guests, existing_meetings, trial, course, strict=False)
        if result:
            return result, 1000 # Heavy penalty for needing relaxed mode
            
        return None, float('inf')

    def _guest_count_by_host(self, hosts: List[int], potential_guests: List[int], trial, course: str) -> Dict[int, int]:
        base = len(potential_guests) // len(hosts)
        remainder = len(potential_guests) % len(hosts)
        counts = [base + (1 if idx < remainder else 0) for idx in range(len(hosts))]
        if remainder:
            seed = trial.suggest_int(f'guest_count_seed_{course}', 0, 10000)
            rng = random.Random(seed)
            rng.shuffle(counts)
        return dict(zip(hosts, counts))

    def _attempt_assignment(self, hosts, potential_guests, existing_meetings, trial, course, strict=True):
        available = defaultdict(list)
        for h_id in hosts:
            for g_id in potential_guests:
                if not self._teams_may_meet(h_id, g_id, existing_meetings, strict):
                    continue
                available[h_id].append(g_id)
        
        guest_counts = self._guest_count_by_host(hosts, potential_guests, trial, course)
        
        for h_id in hosts:
            if len(available[h_id]) < guest_counts[h_id]:
                return None
        
        # Strategy
        strategy_suffix = f"{course}_{'strict' if strict else 'relaxed'}"
        strategy = trial.suggest_categorical(f'strategy_{strategy_suffix}', ['greedy', 'balanced', 'random'])
        
        sorted_hosts = hosts.copy()
        if strategy == 'greedy':
            sorted_hosts.sort(key=lambda h: (len(available[h]) - guest_counts[h], len(available[h])))
        elif strategy == 'random':
            seed = trial.suggest_int(f'seed_{strategy_suffix}', 0, 1000)
            random.seed(seed)
            random.shuffle(sorted_hosts)
            
        return self._backtrack(sorted_hosts, 0, available, guest_counts, set(), {}, existing_meetings)

    def _backtrack(self, hosts, idx, available, guest_counts, used_guests, current_assignment, existing_meetings):
        if idx == len(hosts):
            return current_assignment
        
        host = hosts[idx]
        k = guest_counts[host]
        candidates = [g for g in available[host] if g not in used_guests]
        
        # Try combinations of candidates for this host
        import itertools
        valid_combos = []
        count = 0
        for combo in itertools.combinations(candidates, k):
            # Check if guests in combo have met each other OR the host
            possible = True
            # Host vs Guests (already checked in available[host] if strict, but let's be sure if we want global check)
            for g in combo:
                if not self._teams_may_meet(host, g, existing_meetings, strict=True):
                    possible = False
                    break
            if not possible: continue

            # Guests vs Guests
            for g1, g2 in itertools.combinations(combo, 2):
                if not self._teams_may_meet(g1, g2, existing_meetings, strict=True):
                    possible = False
                    break
            if not possible: continue
            
            valid_combos.append(combo)
            count += 1
            if count > 500: break # Heuristic limit
            
        for combo in valid_combos:
            current_assignment[host] = list(combo)
            used_guests.update(combo)
            
            res = self._backtrack(hosts, idx + 1, available, guest_counts, used_guests, current_assignment, existing_meetings)
            if res: return res
            
            used_guests.difference_update(combo)
            del current_assignment[host]
            
        return None

    def _split_hosts_by_course(self, shuffled_ids: List[int]) -> Dict[CourseType, List[int]]:
        courses = [CourseType.STARTER, CourseType.MAIN, CourseType.DESSERT]
        base = len(shuffled_ids) // 3
        remainder = len(shuffled_ids) % 3
        sizes = [base + (1 if idx < remainder else 0) for idx in range(3)]

        course_hosts = {}
        offset = 0
        for course, size in zip(courses, sizes):
            course_hosts[course] = shuffled_ids[offset:offset + size]
            offset += size
        return course_hosts

    def _objective(self, trial):
        teams = self.active_teams
        courses = [CourseType.STARTER, CourseType.MAIN, CourseType.DESSERT]
        
        # 1. Assign Host Courses
        # Each team hosts exactly once
        # Suggest course for each team? No, that might lead to imbalance.
        # Better: Shuffle teams and assigning chunks to courses.
        
        # Original logic suggests per team then penalizes imbalance.
        # Let's improve: split list into 3 random chunks.
        
        shuffled_ids = [t.id for t in teams]
        # Use a seed for shuffling to make it deterministic per trial
        seed = trial.suggest_int('global_seed', 0, 10000)
        rng = random.Random(seed)
        rng.shuffle(shuffled_ids)
        
        course_hosts = self._split_hosts_by_course(shuffled_ids)
        
        # 2. Assign Guests
        assignments = [] # (course, host, [guests])
        meetings = set() # (id1, id2) sorted
        
        total_dist = 0
        
        # Initialize meetings from host assignments? No, hosts don't meet guests until assignment.
        
        for course in courses:
            hosts = course_hosts[course]
            potential_guests = [tid for tid in shuffled_ids if tid not in hosts]
            
            guest_map, penalty = self._find_valid_guest_assignment(hosts, potential_guests, meetings, trial, course.value)
            
            if not guest_map:
                return float('inf')
            
            total_dist += penalty
            
            for h_id, g_ids in guest_map.items():
                assignments.append(MatchResult(course=course, host_id=h_id, guest_ids=g_ids))
                
                # Update meetings
                # Host meets Guests
                for g_id in g_ids:
                    meetings.add(tuple(sorted((h_id, g_id))))
                    # Guests meet each other? YES.
                    # Original logic checked host-guest and guest-guest? 
                    # "Guest-Guest": "trifft bei jedem Gang auf genau zwei andere Teams" -> Host + other Guest Team.
                    # So Guest1 meets Guest2.
                    for g_id2 in g_ids:
                        if g_id != g_id2:
                            meetings.add(tuple(sorted((g_id, g_id2))))
                    
                    # Dist
                    total_dist += self.distance_matrix.get((g_id, h_id), 0)

        # 3. Validation & End Distance
        # Last course location to end location
        # Track last location of each team
        last_loc = {} # team_id: host_id_of_last_course
        
        # We need to know where everyone was at dessert
        dessert_matches = [m for m in assignments if m.course == CourseType.DESSERT]
        for m in dessert_matches:
            # Host was at their own place
            last_loc[m.host_id] = m.host_id
            for g_id in m.guest_ids:
                last_loc[g_id] = m.host_id # They were at host's place
                
        for t_id in shuffled_ids:
            if t_id in last_loc:
                loc_host_id = last_loc[t_id]
                # Distance from that host to end
                # If host is themselves, distance is from them to end
                if loc_host_id in self.distance_to_end:
                    total_dist += self.distance_to_end[loc_host_id]
        
        trial.set_user_attr('assignments', assignments)
        return total_dist

    def optimize(self, n_trials=100) -> DinnerPlan:
        self.build_distance_matrix()
        
        study = optuna.create_study(direction='minimize')
        study.optimize(self._objective, n_trials=n_trials)
        
        best = study.best_trial
        assignments = best.user_attrs.get('assignments')
        
        if not assignments:
            return DinnerPlan([], float('inf'), False)
            
        return DinnerPlan(
            matches=assignments,
            total_distance=best.value,
            is_valid=True
        )
