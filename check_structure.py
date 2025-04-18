import ijson
import argparse
import sys

def check_json_structure(json_file_path, items_to_check=5):
    """Checks the top-level structure of a JSON file for ijson parsing."""
    print(f"Checking top-level structure of: {json_file_path}")
    found_structure = None
    suggested_path = None

    try:
        # Attempt 1: Check if it's an object with keys at the root
        print("\nAttempt 1: Checking for root object structure like { key1: ..., key2: ... }")
        keys_found = []
        iterable_keys = []
        try:
            with open(json_file_path, 'rb') as f:
                parser_keys = ijson.kvitems(f, '') # Get key-value pairs at root
                for i, (key, value) in enumerate(parser_keys):
                    keys_found.append(key)
                    # Check if value seems like a list (ijson often yields prefix for iterables)
                    # This is a heuristic - might not be perfect
                    if isinstance(value, (list, tuple)) or 'item' in str(type(value)):
                         iterable_keys.append(key)
                         print(f"  - Found top-level key: '{key}' (appears iterable)")
                    else:
                         print(f"  - Found top-level key: '{key}' (type: {type(value)})")
                    if len(keys_found) >= items_to_check * 2 : break # Limit how many keys we check
            if keys_found:
                print(f"  --> Found top-level keys: {keys_found}")
                if iterable_keys:
                    print(f"  --> Iterable keys found: {iterable_keys}. The message array might be under one of these.")
                    # Suggest the first iterable key found as the likely path
                    suggested_path = f"{iterable_keys[0]}.item"
                    found_structure = "object"
                else:
                    print("  --> No obvious iterable arrays found under top-level keys.")
            else:
                print("  --> No top-level keys found this way.")

        except Exception as e:
            print(f"  --> Failed to parse as a top-level object: {e}")

        # Attempt 2: Check if it's an array at the root
        if not found_structure: # Only try if Attempt 1 didn't find anything useful
            print("\nAttempt 2: Checking for root array structure like [ {}, {}, ... ]")
            items_found_count = 0
            try:
                with open(json_file_path, 'rb') as f:
                    parser_array = ijson.items(f, 'item') # Iterate items in root array
                    for i, item in enumerate(parser_array):
                        items_found_count += 1
                        print(f"  - Found root array item {i} (type: {type(item)})")
                        if isinstance(item, dict):
                             print(f"    First few keys: {list(item.keys())[:5]}...")
                        if items_found_count >= items_to_check: break
                if items_found_count > 0:
                    print(f"  --> Found items directly in a root array.")
                    suggested_path = "item"
                    found_structure = "array"
                else:
                    print("  --> No items found in root array.")
            except Exception as e:
                 print(f"  --> Failed to parse as root array: {e}")

        # --- Output Suggestion ---
        print("\n--- Conclusion ---")
        if suggested_path:
            print(f"The JSON seems to be a root '{found_structure}'.")
            print(f"Try using the ijson path prefix: '{suggested_path}' in the main script.")
            print(f"Example: parser = ijson.items(f, '{suggested_path}')")
        else:
            print("Could not automatically determine the structure or message array location.")
            print("You may need to manually inspect the start of the file (e.g., using 'head' or a text editor that handles large files)")
            print("to find the key that contains the list of messages (often 'messages' or similar).")
            print("Then, adjust the ijson path in the main script accordingly (e.g., 'messages.item').")


    except FileNotFoundError:
        print(f"Error: File not found: {json_file_path}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnose the structure of a large JSON file for ijson parsing.")
    parser.add_argument("input_file", help="Path to the large JSON file.")
    args = parser.parse_args()
    check_json_structure(args.input_file)