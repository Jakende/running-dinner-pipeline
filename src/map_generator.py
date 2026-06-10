import os
import html
import folium
import requests
import logging
from typing import List, Dict, Tuple
from .models import DinnerPlan, Team, CourseType

logger = logging.getLogger(__name__)

COURSE_LABELS = {
    'starter': 'Vorspeise / Starter',
    'main': 'Hauptgang / Main course',
    'dessert': 'Dessert',
}

def get_route(p1: Tuple[float, float], p2: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Get bicycle route using OSRM API."""
    url = f"http://router.project-osrm.org/route/v1/bicycle/{p1[1]},{p1[0]};{p2[1]},{p2[0]}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data['code'] == 'Ok':
                # OSRM returns [lon, lat], folium needs [lat, lon]
                coords = data['routes'][0]['geometry']['coordinates']
                return [[c[1], c[0]] for c in coords]
    except Exception as e:
        logger.error(f"Routing error: {e}")
    
    # Fallback to straight line
    return [list(p1), list(p2)]

def generate_team_maps(plan: DinnerPlan, teams: List[Team], output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    temp_map = {t.id: t for t in teams}
    
    # Map for each team
    for team in teams:
        # Find their schedule
        home_pos = (team.latitude, team.longitude)
        
        # Course locations
        courses = [CourseType.STARTER, CourseType.MAIN, CourseType.DESSERT]
        stops = []
        
        for course in courses:
            # Find the match where THIS team is either host or guest
            match = next((m for m in plan.matches if m.course == course and (m.host_id == team.id or team.id in m.guest_ids)), None)
            if match:
                host = temp_map[match.host_id]
                stops.append({
                    'type': course.value,
                    'is_hosting': match.host_id == team.id,
                    'pos': (host.latitude, host.longitude),
                    'address': host.full_address,
                    'hints': host.hints or ''
                })
        
        if not stops:
            continue

        # Create Map
        m = folium.Map(location=[team.latitude, team.longitude], zoom_start=14, tiles="OpenStreetMap")
        
        # Add Home Marker
        folium.Marker(
            home_pos, 
            popup="Home / Start", 
            icon=folium.Icon(color='black', icon='home')
        ).add_to(m)

        # Build path: Home -> Starter -> Main -> Dessert -> Home
        full_path_points = [home_pos] + [s['pos'] for s in stops] + [home_pos]
        
        # Add markers and routes
        colors = {'starter': 'green', 'main': 'blue', 'dessert': 'purple'}
        
        for i, stop in enumerate(stops):
            color = colors.get(stop['type'], 'red')
            course_label = COURSE_LABELS.get(stop['type'], stop['type'].capitalize())
            if stop['is_hosting']:
                color = 'orange'
                label = f"{course_label}: Ihr richtet diesen Gang aus / You host this course"
            else:
                label = course_label

            popup_lines = [
                f"<b>{html.escape(label)}</b>",
                html.escape(stop['address']),
            ]
            if stop['hints']:
                popup_lines.append(f"Hinweise / Notes: {html.escape(stop['hints'])}")
            
            folium.Marker(
                stop['pos'],
                popup="<br>".join(popup_lines),
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(m)

        # Routes
        for i in range(len(full_path_points) - 1):
            p1 = full_path_points[i]
            p2 = full_path_points[i+1]
            route_coords = get_route(p1, p2)
            folium.PolyLine(route_coords, color='blue', weight=4, opacity=0.6, dash_array='5, 10' if i == len(full_path_points)-2 else None).add_to(m)

        # Save
        fname = f"Map_{team.name1}_{team.name2}_{team.id}.html".replace(" ", "_").replace("/", "-")
        m.save(os.path.join(output_dir, fname))
        
    logger.info(f"Generated maps for {len(teams)} teams in {output_dir}")
