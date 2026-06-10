import os
import json
import folium
from folium import plugins
from typing import List, Dict, Tuple
from .models import DinnerPlan, Team, CourseType
from .map_generator import get_route
import logging

logger = logging.getLogger(__name__)

def generate_aggregated_map(plan: DinnerPlan, teams: List[Team], output_path: str):
    temp_map = {t.id: t for t in teams}
    
    # Calculate all routes and distances first
    team_routes = {}
    team_stats = {}
    
    for team in teams:
        home_pos = (team.latitude, team.longitude)
        stops = []
        for course in [CourseType.STARTER, CourseType.MAIN, CourseType.DESSERT]:
            match = next((m for m in plan.matches if m.course == course and (m.host_id == team.id or team.id in m.guest_ids)), None)
            if match:
                host = temp_map[match.host_id]
                stops.append((host.latitude, host.longitude))
        
        full_path = [home_pos] + stops + [home_pos]
        route_segments = []
        total_dist = 0
        for i in range(len(full_path)-1):
            seg = get_route(full_path[i], full_path[i+1])
            route_segments.append(seg)
            # Calculate distance for this segment
            # Simple Euclidean/Haversine if we don't have OSRM distance, 
            # but OSRM gives us the path. Let's estimate from coordinates for now
            # or better: we could get distance from OSRM if we modified get_route
            # For now, let's just sum up the segments roughly.
            from geopy.distance import geodesic
            for j in range(len(seg)-1):
                total_dist += geodesic(seg[j], seg[j+1]).km
        
        team_routes[team.id] = route_segments
        team_stats[team.id] = round(total_dist, 2)

    # Base Map
    freising_center = [48.401, 11.745]
    m = folium.Map(location=freising_center, zoom_start=13, tiles="OpenStreetMap")
    
    # Create FeatureGroups for each team's route (to allow toggling)
    route_groups = {}
    for team in teams:
        fg = folium.FeatureGroup(name=f"Route: {team.team_name}", show=False)
        for seg in team_routes[team.id]:
            folium.PolyLine(seg, color='blue', weight=3, opacity=0.5).add_to(fg)
        fg.add_to(m)
        route_groups[team.id] = fg

    # Mark Hosting Locations
    # Every team hosts once
    for match in plan.matches:
        host = temp_map[match.host_id]
        guests = [temp_map[gid] for gid in match.guest_ids]
        
        popup_html = f"""
        <div style='width: 250px;'>
            <b>{host.team_name}</b> (Host)<br>
            <i>Course: {match.course.value.capitalize()}</i><br>
            <hr>
            <b>Participants:</b><br>
            1. {host.name1}<br>
            2. {host.name2}<br>
        """
        for i, g in enumerate(guests, 1):
            popup_html += f"{i*2+1}. {g.name1}<br>{i*2+2}. {g.name2}<br>"
            
        popup_html += f"""
        <hr>
        <b>Address:</b> {host.address_street}<br>
        <b>Diet:</b> {host.diet.value}<br>
        </div>
        """
        
        color = 'green' if match.course == CourseType.STARTER else 'blue' if match.course == CourseType.MAIN else 'purple'
        
        folium.Marker(
            [host.latitude, host.longitude],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{host.team_name} ({match.course.value})",
            icon=folium.Icon(color=color, icon='cutlery')
        ).add_to(m)

    # Search and Filter
    # Add Search plugin for markers
    # To use Search, we need to put markers in a group
    # But we already have markers. Let's create a dedicated GeoJSON or use MarkerCluster
    
    # Custom Sidebar with Statistics
    stats_html = """
    <div id="stats-box" style="position: fixed; top: 10px; right: 10px; width: 200px; max-height: 80%; overflow-y: auto; background: white; z-index: 1000; padding: 10px; border: 2px solid black; opacity: 0.9;">
        <h4>Team Stats (km)</h4>
        <ul style="list-style: none; padding: 0;">
    """
    # Sort teams by distance
    sorted_teams = sorted(teams, key=lambda t: team_stats[t.id], reverse=True)
    for t in sorted_teams:
        stats_html += f"<li><b>{t.name1.split()[0]} & {t.name2.split()[0]}</b>: {team_stats[t.id]}</li>"
    stats_html += "</ul></div>"
    m.get_root().html.add_child(folium.Element(stats_html))

    # Add LayerControl for routes
    folium.LayerControl(collapsed=True).add_to(m)
    
    # Add Search
    # We'll add a layer of invivible markers with team names for search
    search_group = folium.FeatureGroup(name="Search Layer", show=False)
    for t in teams:
        folium.Marker(
            [t.latitude, t.longitude],
            tooltip=t.team_name,
            icon=folium.Icon(color='white', icon_color='white', opacity=0) # Hidden marker
        ).add_to(search_group)
    search_group.add_to(m)
    
    plugins.Search(
        layer=search_group,
        geom_type="Point",
        placeholder="Search for team...",
        collapsed=False,
        search_label="tooltip"
    ).add_to(m)

    m.save(output_path)
    logger.info(f"Aggregated map saved to {output_path}")
