import os
import sys
import uuid

# Ensure local folder imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from main import process_scan, get_db_connection
except ImportError as e:
    print(f"Error: Could not import scan engine from main.py. Make sure you run this script in the synology directory. Error: {e}")
    sys.exit(1)

def run_manual_scan():
    if len(sys.argv) < 2:
        print("Usage: python manual_scan.py <folder_path_to_scan>")
        print("Example: python manual_scan.py /volume1/photo")
        sys.exit(1)

    target_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(target_path):
        print(f"Error: Target path '{target_path}' does not exist on this machine.")
        sys.exit(1)

    scan_id = str(uuid.uuid4())
    print(f"Connecting to database...")
    
    try:
        conn = get_db_connection()
    except Exception as e:
        print(f"Error: Database connection failed. Verify your environment variables (.env). Error: {e}")
        sys.exit(1)

    try:
        # Initialize scan record in DB to satisfy foreign keys
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO nas_scans (id, path, status) VALUES (%s, %s, 'pending')",
                (scan_id, target_path)
            )
            conn.commit()
        
        print(f"Scan initialized in database [Scan ID: {scan_id}]. Running crawl...")
        print(f"Scanning target path: {target_path}")
        print("Please wait, extracting metadata...")
        
        # Execute the scanner routine synchronously in console
        process_scan(scan_id, target_path)
        
        print("\n[SUCCESS] Manual library scan completed successfully.")
    except Exception as e:
        print(f"\n[FAILED] Manual scan interrupted: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_manual_scan()
