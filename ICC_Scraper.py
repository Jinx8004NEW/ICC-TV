import requests
import time
import os
import argparse
from datetime import datetime, timedelta

def get_with_retries(url, retries=5, initial_sleep=5, timeout=10):
    sleep_time = initial_sleep
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception:
            if attempt == retries - 1: return None
            time.sleep(sleep_time)
            sleep_time *= 2

def fetch_and_filter_videos(base_url, target_video_status_list=None, target_workflow=None, max_skip=None):
    all_filtered_videos = []
    skip = 0
    while True:
        api_url = f"{base_url}/v2/content/en-gb/videos?$skip={skip}&$limit=100"
        response = get_with_retries(api_url)
        if response is None: break
        data = response.json()
        items = data.get("items", [])
        if not items: break
        for item in items:
            fields = item.get("fields", {})
            if (target_video_status_list is None or fields.get("videoStatus") in target_video_status_list) and \
               (target_workflow is None or fields.get("workflow") == target_workflow):
                all_filtered_videos.append(item)
        skip += 100
        if max_skip and skip >= max_skip: break
        time.sleep(1)
    return all_filtered_videos

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-OD", action="store_true")
    args = parser.parse_args()

    BASE_URL = "https://dapi.icc-cricket.com"
    txt_path = "ICC_Events.txt"
    
    if args.OD:
        target_status, max_skip_val, target_wf = ["OnDemand"], 400, None
    else:
        target_status, max_skip_val, target_wf = ["Scheduled", "Live"], 3000, "LIVE"

    videos = fetch_and_filter_videos(BASE_URL, target_status, target_wf, max_skip_val)

    # 1. Load existing data safely
    existing_events = {}
    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "|" in line:
                    event_id = line.split("|")[0].strip()
                    existing_events[event_id] = line
    else:
        print(f"{txt_path} not found. A new file will be created.")

    # 2. Add only NEW events
    initial_count = len(existing_events)
    for item in videos:
        fields = item.get("fields", {})
        event_id = str(fields.get("videoId"))
        if event_id not in existing_events:
            title = item.get("title", "No Title").replace(":", "")
            scheduled = fields.get("scheduledStartTime")
            status = fields.get("videoStatus")
            existing_events[event_id] = f"{event_id} | {title} | {scheduled} | {status}"

    # 3. Save if new data was found OR if file doesn't exist yet
    if len(existing_events) > initial_count or not os.path.exists(txt_path):
        final_list = list(existing_events.values())
        with open(txt_path, "w", encoding="utf-8") as f:
            for line in final_list:
                f.write(line + "\n")
        print(f"Success: File updated. Total events: {len(existing_events)}")
    else:
        print("No new events found. File remains unchanged.")
