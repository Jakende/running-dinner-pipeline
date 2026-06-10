import sqlite3
import json

def check_geocoding():
    conn = sqlite3.connect('data/intermediate/dinner.db')
    cursor = conn.cursor()
    cursor.execute("SELECT full_address, latitude, longitude, success FROM geocoding_cache")
    rows = cursor.fetchall()
    print("Geocoding Cache:")
    for row in rows:
        print(f"Address: {row[0]}, Success: {row[3]}, Lat: {row[1]}, Lon: {row[2]}")
    conn.close()

if __name__ == "__main__":
    check_geocoding()
