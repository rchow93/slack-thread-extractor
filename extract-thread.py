import ijson
import json
import argparse
import sys
from collections import defaultdict
import os
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Functions extract_text_from_element and extract_text_from_message remain unchanged ---
# (Keep the versions from the previous good script)
def extract_text_from_element(element):
    """Recursively extracts text from a Slack block element."""
    text_parts = []
    if isinstance(element, dict):
        element_type = element.get('type')
        if element_type == 'text':
            text_parts.append(element.get('text', ''))
        elif element_type == 'user':
            # Represent user mention as <@USER_ID>
            text_parts.append(f"<@{element.get('user_id', '')}>")
        elif element_type == 'link':
            # Use link text if available, otherwise URL
            text_parts.append(element.get('text') or element.get('url', ''))
        elif element_type == 'emoji':
            # Represent emoji as :emoji_name:
            text_parts.append(f":{element.get('name', '')}:")
        elif element_type == 'usergroup':
             text_parts.append(f"<!subteam^{element.get('usergroup_id', '')}>")
        elif element_type == 'channel':
             text_parts.append(f"<#{element.get('channel_id', '')}>")
        # Recurse into sub-elements if present (e.g., in rich_text_section, rich_text_list)
        if 'elements' in element and isinstance(element['elements'], list):
            for sub_element in element['elements']:
                text_parts.extend(extract_text_from_element(sub_element))
        # Handle text within specific block types directly if needed (e.g., section text)
        elif 'text' in element and isinstance(element['text'], dict):
             text_parts.extend(extract_text_from_element(element['text']))
        elif 'title' in element and isinstance(element['title'], dict): # e.g., context block title
             text_parts.extend(extract_text_from_element(element['title']))

    elif isinstance(element, list): # Handle cases where elements are directly in a list
        for sub_element in element:
            text_parts.extend(extract_text_from_element(sub_element))

    return text_parts

def extract_text_from_message(message):
    """Extracts meaningful text from a Slack message object, prioritizing blocks."""
    text_content = ""
    try:
        if 'blocks' in message and message['blocks']:
            all_texts = []
            for block in message['blocks']:
                # Extract text from elements within the block
                if 'elements' in block and isinstance(block['elements'], list):
                     for element in block['elements']:
                          all_texts.extend(extract_text_from_element(element))
                # Also check for primary text/title fields common in blocks like section, header, context
                if 'text' in block and isinstance(block['text'], dict):
                     all_texts.extend(extract_text_from_element(block['text']))
                if 'title' in block and isinstance(block['title'], dict):
                     all_texts.extend(extract_text_from_element(block['title']))

            text_content = " ".join(part for part in all_texts if part).strip() # Join extracted parts

        # Fallback or supplement with the top-level text field if block parsing yields nothing
        if not text_content and 'text' in message:
             text_content = message.get('text', '')

        # Final check for empty content
        if not text_content:
             if 'attachments' in message and message['attachments']:
                 for att in message['attachments']:
                      text_content = att.get('text') or att.get('fallback')
                      if text_content: break

    except Exception as e:
        logging.warning(f"Error parsing blocks/text for message ts={message.get('ts')}: {e}")
        text_content = message.get('text', '')

    return text_content or "" # Ensure we always return a string


def process_slack_export(input_file_path, output_base_name, start_emoji, end_emoji, records_per_file=5000, include_bots=False):
    """
    Parses a large Slack export (structured as array of chunks), identifies
    complete support threads using reactions, extracts conversations, formats
    them as JSONL, and saves them into split files.
    """
    collected_threads = defaultdict(list)
    threads_with_start = set()
    threads_with_end = set()
    processed_messages = 0
    processed_chunks = 0

    logging.info(f"Starting processing of {input_file_path}")
    logging.info(f"Assuming structure: Array of chunks, each with a 'messages' key.")
    logging.info(f"Looking for threads marked with start=':{start_emoji}:' and end=':{end_emoji}:' reactions.")
    logging.info(f"Output base name: {output_base_name}, Records per file: {records_per_file}")
    logging.info(f"Include bot messages: {include_bots}")

    try:
        with open(input_file_path, 'rb') as f:
            # Use 'item' because the root is an array of chunks
            parser = ijson.items(f, 'item')
            chunk_count = 0

            # Outer loop: Iterate through the CHUNKS in the root array
            for chunk in parser:
                chunk_count += 1
                if not isinstance(chunk, dict) or 'messages' not in chunk:
                    logging.warning(f"Skipping item {chunk_count} in root array as it's not a dictionary with a 'messages' key.")
                    continue

                # Log progress through chunks periodically if the file is very large
                if chunk_count % 20 == 0: # Adjust frequency as needed
                    logging.info(f"Processing chunk #{chunk_count}...")

                # Inner loop: Iterate through the actual MESSAGES within this chunk
                messages_in_chunk = chunk.get('messages', [])
                if not isinstance(messages_in_chunk, list):
                     logging.warning(f"Chunk {chunk_count} 'messages' key does not contain a list. Skipping.")
                     continue

                for message in messages_in_chunk: # 'message' is now the actual message object
                    processed_messages += 1
                    if processed_messages % 25000 == 0: # Log based on total messages processed
                        logging.info(f"Processed {processed_messages} total messages...")

                    # --- Start of individual message processing logic ---
                    if not isinstance(message, dict) or message.get('type') != 'message' or 'ts' not in message:
                        # Skip things that aren't valid message dictionaries
                        continue

                    thread_ts = message.get('thread_ts', message.get('ts')) # Use message ts if it's a parent

                    msg_data = {
                        'ts': message.get('ts'),
                        'thread_ts': message.get('thread_ts'),
                        'user': message.get('user'),
                        'bot_id': message.get('bot_id'),
                        'username': message.get('username'),
                        'subtype': message.get('subtype'),
                        'text': message.get('text'),
                        'blocks': message.get('blocks'),
                        'reactions': message.get('reactions', []),
                        'files': message.get('files')
                    }
                    collected_threads[thread_ts].append(msg_data)

                    # Check reactions on this specific message
                    has_start = False
                    has_end = False
                    for reaction in msg_data['reactions']:
                        if reaction.get('name') == start_emoji:
                            has_start = True
                        if reaction.get('name') == end_emoji:
                            has_end = True

                    if has_start:
                        threads_with_start.add(thread_ts)
                    if has_end:
                        threads_with_end.add(thread_ts)
                    # --- End of individual message processing logic ---

            # --- End of file parsing ---

    except FileNotFoundError:
        logging.error(f"Error: Input file not found at {input_file_path}")
        return
    except ijson.JSONError as e:
        logging.error(f"Error parsing JSON: {e}")
        logging.error("Check if the file structure matches the expected Array-of-Chunks format.")
        return
    except Exception as e:
        logging.error(f"An unexpected error occurred during parsing: {e}", exc_info=True)
        return

    logging.info(f"Finished initial scan. Processed {chunk_count} chunks and {processed_messages} total messages.")
    logging.info(f"Found {len(collected_threads)} unique thread roots.") # This should now be > 0
    logging.info(f"Found {len(threads_with_start)} threads with start marker reaction.")
    logging.info(f"Found {len(threads_with_end)} threads with end marker reaction.")

    # Identify threads that have BOTH markers
    complete_threads_ts = threads_with_start.intersection(threads_with_end)
    logging.info(f"Found {len(complete_threads_ts)} candidate threads with both start and end markers.")

    if not complete_threads_ts:
        logging.warning("No threads found with both start and end reaction markers. Exiting.")
        return

    # --- Process complete threads and write output ---
    output_file = None
    file_counter = 1
    record_counter_in_file = 0
    total_records_written = 0
    output_filename = "" # Initialize

    try:
        for thread_ts in sorted(list(complete_threads_ts)):
            thread_messages = collected_threads.get(thread_ts, [])
            if not thread_messages: continue

            sorted_thread = sorted(thread_messages, key=lambda m: float(m['ts']))
            if not sorted_thread: continue

            prompt_message = sorted_thread[0]
            prompt_text = extract_text_from_message(prompt_message).strip()

            if not prompt_text:
                logging.warning(f"Skipping thread {thread_ts} due to empty first message.")
                continue

            completion_parts = []
            for i, msg in enumerate(sorted_thread[1:]):
                is_bot = msg.get('subtype') == 'bot_message' or msg.get('bot_id')
                if not include_bots and is_bot: continue

                msg_text = extract_text_from_message(msg).strip()
                if not msg_text and not msg.get('files'): continue # Skip empty non-file messages

                if is_bot:
                    bot_name = msg.get('username', msg.get('bot_id', 'Bot'))
                    prefix = f"Bot [{bot_name}]:"
                else:
                    prefix = f"User [{msg.get('user', 'Unknown')}]:"

                completion_parts.append(f"{prefix} {msg_text}")

            completion_text = "\n".join(completion_parts).strip()

            if len(sorted_thread) > 1 and not completion_text:
                 # Log if replies existed but resulted in no text (might be only files/joins)
                 logging.debug(f"Thread {thread_ts} had replies but yielded empty completion text after filtering.")
                 # Decide whether to skip or keep with empty completion
                 # continue # Option to skip
                 pass # Option to keep with empty completion

            output_record = {"prompt": prompt_text, "completion": completion_text}

            # Handle file splitting
            if output_file is None or record_counter_in_file >= records_per_file:
                if output_file:
                    output_file.close()
                    logging.info(f"Closed output file: {output_filename}")

                output_filename = f"{output_base_name}_part_{file_counter}.jsonl"
                logging.info(f"Opening new output file: {output_filename}")
                output_file = open(output_filename, 'w', encoding='utf-8')
                file_counter += 1
                record_counter_in_file = 0

            output_file.write(json.dumps(output_record, ensure_ascii=False) + '\n')
            record_counter_in_file += 1
            total_records_written += 1

            if total_records_written % 100 == 0 and total_records_written > 0:
                 logging.info(f"Written {total_records_written} records...")

    except Exception as e:
        logging.error(f"An error occurred during thread processing/writing: {e}", exc_info=True)
    finally:
        if output_file and not output_file.closed:
            output_file.close()
            logging.info(f"Closed final output file: {output_filename}")

    logging.info(f"Processing complete. Total records written: {total_records_written}")


# --- Command Line Argument Parsing ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Slack JSON export (array of chunks) into JSONL for fine-tuning.")
    parser.add_argument("input_file", help="Path to the large Slack JSON export file (e.g., export.json or export.json.txt)")
    parser.add_argument("output_base", help="Base name for output JSONL files (e.g., 'support_threads'). Files will be named like 'support_threads_part_1.jsonl'")
    parser.add_argument("--start_emoji", required=True, help="Exact name of the start emoji reaction (e.g., 'hand')")
    parser.add_argument("--end_emoji", required=True, help="Exact name of the end emoji reaction (e.g., 'done')")
    parser.add_argument("--records_per_file", type=int, default=5000, help="Maximum number of JSONL records per output file (default: 5000)")
    parser.add_argument("--include_bots", action='store_true', help="Include messages from bots in the 'completion' text.")

    args = parser.parse_args()

    process_slack_export(
        args.input_file,
        args.output_base,
        args.start_emoji,
        args.end_emoji,
        args.records_per_file,
        args.include_bots
    )