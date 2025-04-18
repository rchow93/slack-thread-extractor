
```markdown
# Slack Thread Extractor for Fine-Tuning

This Python script processes large Slack JSON exports (specifically those structured as an array of message chunks) to extract conversation threads marked by specific start and end emoji reactions. It formats these threads into a JSONL (JSON Lines) file suitable for fine-tuning language models, where each line contains a prompt (the initial message) and a completion (the subsequent messages in the thread).

## Features

*   Parses potentially very large Slack JSON export files efficiently using `ijson`.
*   Identifies conversation threads based on start and end emoji reactions applied to any message within the thread.
*   Extracts text content from messages, prioritizing Slack's Block Kit structure, but falling back to the basic `text` field. Handles common elements like user mentions, links, channels, and emojis.
*   Formats extracted threads into a `prompt`/`completion` structure.
*   Optionally includes or excludes messages from bots in the `completion`.
*   Splits the output into multiple JSONL files to manage size.
*   Provides informative logging during processing.

## Prerequisites

*   Python 3.6+
*   The `ijson` library:
    ```bash
    pip install ijson
    ```

## Input Data Format

**Crucially, this script expects the input JSON file to be structured as a top-level JSON array `[...]`, where each element in the array is a "chunk" dictionary. Each chunk dictionary must contain a key named `"messages"`, which holds an array `[...]` of actual Slack message objects.**

Example Structure (`your_export.json`):

```json
[
  {
    "messages": [
      {
        "type": "message",
        "user": "U123ABC",
        "ts": "1678886401.000100",
        "text": "Can someone help with issue X?",
        // ... other message fields ...
      },
      {
        "type": "message",
        "user": "U456DEF",
        "ts": "1678886462.000200",
        "thread_ts": "1678886401.000100",
        "text": "I can take a look.",
        // ... other message fields ...
      }
      // ... more messages in this chunk ...
    ]
  },
  {
    "messages": [
      {
        "type": "message",
        "user": "U123ABC",
        "ts": "1678886523.000300",
        "thread_ts": "1678886401.000100",
        "text": "Thanks! It's related to the API endpoint /foo.",
        "reactions": [
            { "name": "hand", "users": ["U456DEF"], "count": 1 } // Start Emoji
        ]
        // ... other message fields ...
      },
      {
        "type": "message",
        "user": "U456DEF",
        "ts": "1678886584.000400",
        "thread_ts": "1678886401.000100",
        "text": "Okay, found the problem. It's fixed now.",
        "reactions": [
            { "name": "white_check_mark", "users": ["U123ABC"], "count": 1 } // End Emoji
        ]
        // ... other message fields ...
      }
      // ... more messages in this chunk ...
    ]
  }
  // ... more chunks ...
]
```

*If your export is simply a flat array of messages at the root level, you will need to modify the script or pre-process your data.*

## Usage

Run the script from your command line:

```bash
python extract-thread.py <input_file> <output_base> --start_emoji <emoji_name> --end_emoji <emoji_name> [options]
```

### Arguments

*   `input_file`: (Required) Path to the Slack JSON export file (e.g., `export.json`, `channel_export.json.txt`).
*   `output_base`: (Required) Base name for the output JSONL files. Files will be named `<output_base>_part_1.jsonl`, `<output_base>_part_2.jsonl`, etc. (e.g., `support_threads`).
*   `--start_emoji`: (Required) The exact name of the emoji reaction used to mark the *start* or *inclusion* of a relevant thread (e.g., `hand`, `ticket`, `question`). **Do not include colons (`:`)**.
*   `--end_emoji`: (Required) The exact name of the emoji reaction used to mark the *end* or *completion* of a relevant thread (e.g., `done`, `white_check_mark`, `heavy_check_mark`). **Do not include colons (`:`)**.
*   `--records_per_file` (Optional) Maximum number of JSONL records (threads) per output file. Defaults to `5000`.
*   `--include_bots` (Optional) If this flag is present, messages identified as being from bots will be included in the `completion` text, prefixed with `Bot [Bot Name]:`. By default, bot messages are excluded.

### Example

```bash
python extract-thread.py slack_export.json training_data --start_emoji ticket --end_emoji heavy_check_mark --records_per_file 10000 --include_bots
```

This command will:
1.  Read `slack_export.json` (assuming the array-of-chunks structure).
2.  Look for threads where at least one message has a `:ticket:` reaction AND at least one message (could be the same or different) has a `:heavy_check_mark:` reaction.
3.  Extract the first message of each identified thread as the `prompt`.
4.  Extract subsequent messages (including bot messages) as the `completion`, prefixing them with `User [UserID]:` or `Bot [BotName]:`.
5.  Write the output to files named `training_data_part_1.jsonl`, `training_data_part_2.jsonl`, etc., with a maximum of 10,000 records per file.

## Output Format

The script generates one or more `.jsonl` files. Each line in these files is a valid JSON object representing one extracted thread:

```json
{"prompt": "First message text of the thread...", "completion": "User [U123ABC]: Second message text...\nUser [U456DEF]: Third message text...\nBot [BotID]: Bot reply text..."}
{"prompt": "First message of another thread...", "completion": "User [UXYZ123]: Reply text..."}
```

*   `prompt`: Contains the extracted text content of the first message in the thread.
*   `completion`: Contains the concatenated text content of all subsequent messages in the thread (respecting the `--include_bots` flag), ordered by timestamp. Each message is prefixed with `User [UserID]:` or `Bot [BotName/BotID]:` and separated by a newline character (`\n`).

## Important Notes

*   **Emoji Names:** Ensure the `--start_emoji` and `--end_emoji` names exactly match the internal Slack names for the emojis (e.g., `white_check_mark`, not `✅`). You can usually find these by inspecting the reaction data in the JSON export.
*   **Input Structure:** The script is specifically designed for the "array of chunks" structure described above. Verify your export format.
*   **Memory Usage:** Using `ijson` helps process large files without loading everything into memory at once. However, collecting thread data might still consume significant memory depending on the number and length of threads.
*   **Text Extraction:** The script attempts to robustly extract text from various Slack message structures (blocks, elements, fallback text). However, complex or unusual message formats might not be fully captured. User mentions (`<@USERID>`), channel links (`<#CHANNELID>`), user group mentions (`<!subteam^GROUPID>`), links, and emojis are represented in a text-based format.
```
