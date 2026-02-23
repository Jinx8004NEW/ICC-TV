import requests
import time
import os
import argparse
from datetime import datetime, timedelta

# -----------------------------
# Retry logic for API requests
# -----------------------------
def get_with_retries(url, retries=5, initial_sleep=5, timeout=10):
    sleep_time = initial_sleep
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(sleep_time)
            sleep_time *= 2

# --------------------------------------
# Fetch and filter ICC videos from API
# --------------------------------------
def fetch_and_filter_videos(
    base_url,
    language_locale="en-gb",
    target_video_status_list=None,
    target_workflow=None,
    limit_per_request=100,
    max_skip=None
):
    all_filtered_videos = []
    skip = 0
    while True:
        api_url = (
            f"{base_url}/v2/content/{language_locale}/videos"
            f"?$skip={skip}&$limit={limit_per_request}"
        )
        response = get_with_retries(api_url)
        if response is None:
            break
        data = response.json()
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            fields = item.get("fields", {})
            if (
                (target_video_status_list is None or
                 fields.get("videoStatus") in target_video_status_list)
                and
                (target_workflow is None or
                 fields.get("workflow") == target_workflow)
            ):
                all_filtered_videos.append(item)
        skip += limit_per_request
        if max_skip and skip >= max_skip:
            break
        time.sleep(2)
    return all_filtered_videos

# -----------------------------
# Main Execution
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-OD", action="store_true")
    args = parser.parse_args()

    BASE_URL = "https://dapi.icc-cricket.com"

    if args.OD:
        target_status = ["OnDemand"]
        max_skip_val = 400
        target_wf = None
    else:
        target_status = ["Scheduled", "Live"]
        max_skip_val = 3000
        target_wf = "LIVE"

    videos = fetch_and_filter_videos(
        BASE_URL,
        target_video_status_list=target_status,
        target_workflow=target_wf,
        max_skip=max_skip_val
    )

    # Path changed to current directory for GitHub compatibility
    txt_path = "ICC_Events.txt"
    three_months_ago = datetime.now() - timedelta(days=90)

    existing_events = {}

    # Load existing file if present
    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    event_id = line.split("|")[0].strip()
                    existing_events[event_id] = line.strip()

    # Add new events
    for item in videos:
        fields = item.get("fields", {})
        event_id = str(fields.get("videoId"))
        if event_id not in existing_events:
            title = item.get("title", "No Title").replace(":", "")
            scheduled = fields.get("scheduledStartTime")
            status = fields.get("videoStatus")
            existing_events[event_id] = (
                f"{event_id} | {title} | {scheduled} | {status}"
            )

    # Filter last 3 months
    final_list = []
    for line in existing_events.values():
        try:
            dt_string = line.split("|")[2].strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(dt_string)
            if dt > three_months_ago:
                final_list.append((dt, line))
        except Exception:
            final_list.append((datetime.now(), line))

    final_list.sort(key=lambda x: x[0])

    # Write updated file
    with open(txt_path, "w", encoding="utf-8") as f:
        for _, line in final_list:
            f.write(line + "\n")

    print(f"{txt_path} updated successfully.")
