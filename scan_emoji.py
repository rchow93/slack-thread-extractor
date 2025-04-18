import ijson
import json
import argparse
import sys
from collections import Counter

def scan_reaction_emojis(json_file_path, top_n=50):
    """
    Scans a large Slack export JSON file iteratively to find all unique emoji
    names used in reactions and their counts.

    Args:
        json_file_path (str): Path to the large Slack JSON export file.
        top_n (int): How many of the most frequent emojis to display.
    """
    emoji_counts = Counter()
    processed_messages = 0
    reaction_messages_count = 0

    print(f"Starting emoji reaction scan of {json_file_path}...")

    try:
        with open(json_file_path, 'rb') as f: # Open in binary mode for ijson
            # Assuming the JSON is an array of message objects at the root
            parser = ijson.items(f, 'item') # 'item' iterates through array elements

            for message in parser:
                processed_messages += 1
                if processed_messages % 50000 == 0: # Update progress every 50k messages
                    print(f"  Processed {processed_messages} messages... Found {len(emoji_counts)} unique reaction emojis so far.", file=sys.stderr)

                # We only care about messages with reactions
                if message.get('type') == 'message' and 'reactions' in message and message['reactions']:
                    reaction_messages_count += 1
                    for reaction in message['reactions']:
                        emoji_name = reaction.get('name')
                        if emoji_name: # Ensure the emoji has a name
                            emoji_counts[emoji_name] += 1

            # --- End of file processing ---

            print(f"\nScan complete. Processed {processed_messages} total messages.")
            print(f"Found {reaction_messages_count} messages with reactions.")
            if not emoji_counts:
                print("No emoji reactions found in any messages.")
                return

            print(f"\nFound {len(emoji_counts)} unique emoji reactions.")
            print(f"Top {top_n} most frequent emoji reactions:")

            # Sort emojis by frequency, descending
            sorted_emojis = emoji_counts.most_common(top_n)

            for name, count in sorted_emojis:
                print(f"  :{name}:  (used {count} times)")

            if len(emoji_counts) > top_n:
                print(f"\n(Showing top {top_n} out of {len(emoji_counts)} total unique emojis)")


    except FileNotFoundError:
        print(f"Error: Input file not found at {json_file_path}", file=sys.stderr)
    except ijson.JSONError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        print("This might indicate the file is not valid JSON or the structure is unexpected.", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

# --- Command Line Argument Parsing ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan a large Slack JSON export for unique emoji reactions.")
    parser.add_argument("input_file", help="Path to the large Slack JSON export file (e.g., export.json.txt)")
    parser.add_argument("--top", type=int, default=50, help="Number of most frequent emojis to display (default: 50)")

    args = parser.parse_args()

    scan_reaction_emojis(args.input_file, args.top)