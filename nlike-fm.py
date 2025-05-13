import logging
import os
import stat
import time
import curses
import sys
import shutil
import pyperclip
import subprocess
import colors


logging.basicConfig(
    level=logging.ERROR,
    filename=f"{os.path.splitext(os.path.basename(__file__))[0]}.log",
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def log_error(error):
    logging.error(f"{type(error).__name__}: {error}")


def list_files(directory):
    try:
        items = os.listdir(directory)
        directories = [item for item in items if os.path.isdir(os.path.join(directory, item))]
        files = [item for item in items if os.path.isfile(os.path.join(directory, item))]
        return sorted(directories) + sorted(files), None
    except PermissionError:
        return [], "Permission to access the directory is denied."
    except FileNotFoundError:
        return [], "Directory not found."
    except Exception as e:
        log_error(e)
        return [], "Unknown error occurred. Check logs for details."


def format_size(size_in_bytes):
    if size_in_bytes < 0:
        return "Invalid file size"

    units = ["bytes", "KB", "MB", "GB", "TB"]
    size = size_in_bytes
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    return f"{size:.2f} {units[unit_index]}"


def get_file_info(file_path):
    try:
        mode = os.stat(file_path).st_mode
        is_dir = "d" if stat.S_ISDIR(mode) else "-"
        permissions = is_dir + "".join(
            (char if mode & mask else "-")
            for char, mask in zip(
                "rwx" * 3,
                [
                    stat.S_IRUSR,
                    stat.S_IWUSR,
                    stat.S_IXUSR,
                    stat.S_IRGRP,
                    stat.S_IWGRP,
                    stat.S_IXGRP,
                    stat.S_IROTH,
                    stat.S_IWOTH,
                    stat.S_IXOTH,
                ],
            )
        )

        last_modified = time.localtime(os.path.getmtime(file_path))
        date = time.strftime("%d/%m/%Y", last_modified)
        time_formatted = time.strftime("%I:%M %p", last_modified)

        if os.path.isdir(file_path):
            folder_count, file_count = 0, 0
            for root, dirs, files in os.walk(file_path):
                folder_count += len(dirs)
                file_count += len(files)
                break
            size = f"{folder_count} folder(s), {file_count} file(s)"
        else:
            file_size = os.path.getsize(file_path)
            size = format_size(file_size)

        return f"{permissions} {date} {time_formatted} {size}"

    except Exception as e:
        log_error(e)
        return "Error retrieving file information."


def display_files(stdscr, files, current_index, max_height, current_directory):
    start_index = max(0, current_index - max_height + 1)
    end_index = min(len(files), start_index + max_height)

    for index in range(start_index, end_index):
        file = files[index]
        full_path = os.path.join(current_directory, file)
        color = curses.color_pair(2) if os.path.isdir(full_path) else curses.color_pair(3)

        if index == current_index:
            if os.path.isdir(full_path):
                stdscr.addstr(index - start_index + 1, 0, f"> {file}", color | curses.A_REVERSE | curses.A_BOLD)
            else:
                stdscr.addstr(index - start_index + 1, 0, f"- {file}", color | curses.A_REVERSE | curses.A_BOLD)
        else:
            stdscr.addstr(index - start_index + 1, 0, f"  {file}", color)

    if not files:
        stdscr.addstr(1, 0, "", curses.color_pair(1))
        stdscr.addstr(2, 0, "This directory is empty.", curses.color_pair(4))


def validate_directory(directory):
    if not os.path.exists(directory):
        print(f"Error: The path does not exist.")
        sys.exit(1)


def main(stdscr, directories):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    colors.init_colors()
    tab_stack = directories
    current_directory = tab_stack[0]
    current_tab_index = 0
    current_index = 0
    history = [current_directory]
    history_index = 0
    selected_path = None
    error_message = ""
    show_error = False
    last_action = None
    copied_path = None
    cut_path = None
    undo_stack = []
    redo_stack = []
    indicator = "_"

    max_height, max_width = stdscr.getmaxyx()

    while True:
        min_height, min_width = 15, 48
        max_height, max_width = stdscr.getmaxyx()

        if max_height < min_height or max_width < min_width:
            print("WARNING: Terminal size too small!")
            print(f"Minimum size required: {min_width}x{min_height}")
            exit(1)

        stdscr.clear()
        max_display_width = max_width - len("Current Directory: ") - 3

        if len(current_directory) > max_display_width:
            truncated_directory = "..." + current_directory[-max_display_width:]
        else:
            truncated_directory = current_directory

        stdscr.addstr(0, 0, "Current Directory: ", curses.color_pair(1))
        stdscr.addstr(0, len("Current Directory: "), truncated_directory, curses.color_pair(2))
        files, error_loading = list_files(current_directory)

        if error_loading:
            error_message = error_loading
            show_error = True

        display_files(stdscr, files, current_index, max_height - 2, current_directory)

        if show_error and error_message:
            stdscr.addstr(max_height - 1, 0, error_message[: max_width - 1], curses.color_pair(5) | curses.A_BOLD)
        elif files:
            selected_item = files[current_index]
            selected_path = os.path.join(current_directory, selected_item)
            file_info = get_file_info(selected_path)
            usable_width = max_width - 4
            truncated_info = file_info[:usable_width]
            permissions, rest_info = file_info.split(" ", 1)
            stdscr.addstr(max_height - 1, 0, permissions, curses.color_pair(2) | curses.A_BOLD)
            stdscr.addstr(max_height - 1, len(permissions) + 1, rest_info, curses.A_BOLD)
            stdscr.addstr(max_height - 1, max_width - 4, f"[{indicator}]", curses.color_pair(1) | curses.A_BOLD)

        stdscr.refresh()
        key = stdscr.getch()

        if key in [curses.KEY_RIGHT, curses.KEY_LEFT, curses.KEY_UP, curses.KEY_DOWN]:
            show_error = False

        if key == 27:
            break
        elif key == 9:
            tab_stack[current_tab_index] = current_directory
            current_tab_index = (current_tab_index + 1) % len(tab_stack)
            current_directory = tab_stack[current_tab_index]
            history = [current_directory]
            current_index = 0 if len(tab_stack) > 1 else current_index
        elif key == ord("+"):
            show_error = False
            stdscr.addstr(max_height - 1, 0, "Enter a directory path: ", curses.A_BOLD)
            stdscr.refresh()
            stdscr.clrtoeol()

            curses.echo()
            curses.curs_set(1)

            new_path = stdscr.getstr(
                max_height - 1,
                len("Enter a directory path: "),
                max_width - len("Enter a directory path: "),
            )

            curses.noecho()
            curses.curs_set(0)

            new_path = new_path.decode("utf-8")
            if os.path.isdir(new_path):
                tab_stack[current_tab_index] = current_directory
                tab_stack.append(new_path)
                current_tab_index = len(tab_stack) - 1
                current_directory = new_path
                history = [current_directory]
                current_index = 0
            else:
                error_message = "Invalid directory path!"
                show_error = True
        elif ord("1") <= key <= ord("9"):
            tab_index = key - ord("1")
            if tab_index < len(tab_stack):
                tab_stack[current_tab_index] = current_directory
                current_tab_index = tab_index
                current_directory = tab_stack[current_tab_index]
                history = [current_directory]
                current_index = 0 if len(tab_stack) > 1 else current_index
            else:
                show_error = False
                continue
        elif key == curses.KEY_RIGHT:
            if files:
                selected = files[current_index]
                new_path = os.path.join(current_directory, selected)
                if os.path.isdir(new_path):
                    if history_index < len(history) - 1:
                        history = history[: history_index + 1]
                    history.append(new_path)
                    history_index += 1
                    current_directory = new_path
                    current_index = 0
        elif key == curses.KEY_LEFT:
            parent_directory = os.path.dirname(current_directory)
            if parent_directory and os.path.isdir(parent_directory):
                history.append(parent_directory)
                history_index += 1
                current_directory = parent_directory
                tab_stack[current_tab_index] = current_directory
                parent_files, _ = list_files(current_directory)
                prev_folder_name = (os.path.basename(history[-2]) if len(history) > 1 else None)
                current_index = (
                    parent_files.index(prev_folder_name)
                    if prev_folder_name in parent_files
                    else 0
                )
        elif key == curses.KEY_DOWN:
            current_index = (current_index + 1) % len(files) if files else 0
        elif key == curses.KEY_UP:
            current_index = (current_index - 1) % len(files) if files else 0
        elif key == curses.KEY_DC:
            if files:
                stdscr.move(max_height - 1, 0)
                stdscr.clrtoeol()
                stdscr.addstr(max_height - 1, 0, "Delete selected item? [y] Yes, [n] No: ",curses.A_BOLD,)
                stdscr.refresh()

                user_input = stdscr.getch()
                while user_input not in [ord("y"), ord("n")]:
                    user_input = stdscr.getch()

                if user_input == ord("y"):
                    try:
                        if os.path.isdir(selected_path):
                            shutil.rmtree(selected_path)
                        else:
                            os.remove(selected_path)
                        files.pop(current_index)
                        current_index = max(0, current_index - 1)
                        indicator = "_"
                    except FileNotFoundError:
                        error_message = "Error: File or directory not found."
                        show_error = True
                    except PermissionError:
                        error_message = ("Error: Insufficient permissions to delete this item.")
                        show_error = True
                    except Exception as e:
                        log_error(e)
                        error_message = f"Unexpected error: {str(e)}"
                        show_error = True

                if show_error:
                    stdscr.move(max_height - 1, 0)
                    stdscr.clrtoeol()
                    stdscr.addstr(max_height - 1, 0, error_message, curses.color_pair(1))
                    stdscr.refresh()
        elif key == ord("p"):
            selected_item = files[current_index] if files else ""
            selected_path = os.path.join(current_directory, selected_item)
            try:
                pyperclip.copy(selected_path)
                indicator = "P"
            except pyperclip.PyperclipException as e:
                log_error(e)
                error_message = "Clipboard Error: Unable to copy the path."
                show_error = True
        elif key == 10:
            if selected_path and os.path.exists(selected_path):
                try:
                    if sys.platform == "win32":
                        subprocess.run(["start", "", selected_path], shell=True)
                    elif sys.platform == "darwin":
                        subprocess.run(["open", selected_path])
                    else:
                        subprocess.run(["xdg-open", selected_path])
                except Exception as e:
                    log_error(e)
                    error_message = "Error opening file. Check logs for details."
                    show_error = True
        elif key == ord("c"):
            copied_path = selected_path
            last_action = "copy"
            cut_path = None
            indicator = "C"
        elif key == ord("x"):
            cut_path = selected_path
            last_action = "cut"
            copied_path = None
            indicator = "X"
        elif key == ord("v"):
            if last_action in ["copy", "cut"]:
                source_path = copied_path if last_action == "copy" else cut_path
                destination = os.path.join(current_directory, os.path.basename(source_path))

                def prompt_user(prompt_text, valid_keys):
                    stdscr.addstr(max_height - 1, 0, prompt_text, curses.A_BOLD)
                    stdscr.refresh()
                    user_input = stdscr.getch()
                    while user_input not in valid_keys:
                        user_input = stdscr.getch()
                    return user_input

                if last_action == "cut" and os.path.abspath(source_path) == os.path.abspath(destination):
                    user_input = prompt_user(
                        "Source and destination are the same. [s] Skip, [c] Cancel: ",
                        [ord("s"), ord("c")],
                    )

                    if user_input == ord("c") or ord("s"):
                        show_error = False
                        continue
                elif last_action == "copy" and os.path.abspath(source_path) == os.path.abspath(destination):
                    base_name, extension = os.path.splitext(os.path.basename(source_path))
                    new_name = f"{base_name}-copy{extension}"
                    destination = os.path.join(current_directory, new_name)

                    counter = 1
                    while os.path.exists(destination):
                        new_name = f"{base_name}-copy ({counter}){extension}"
                        destination = os.path.join(current_directory, new_name)
                        counter += 1

                    try:
                        if os.path.isdir(source_path):
                            shutil.copytree(source_path, destination)
                        else:
                            shutil.copy2(source_path, destination)

                        undo_stack.append({"action": "copy", "src": source_path, "dst": destination})
                        redo_stack.clear()
                        indicator = "Z"
                        show_error = False
                    except Exception as e:
                        log_error(e)
                        error_message = "Error: Unable to copy the file or directory."
                        show_error = True
                elif os.path.abspath(source_path) != os.path.abspath(destination):
                    if os.path.exists(destination):
                        user_input = prompt_user(
                            "File or directory already exists. [o] Overwrite, [k] Keep both, [c] Cancel: ",
                            [ord("o"), ord("k"), ord("c")],
                        )

                        if user_input == ord("o"):
                            try:
                                if os.path.isdir(source_path):
                                    shutil.copytree(source_path, destination, dirs_exist_ok=True)
                                else:
                                    shutil.copy2(source_path, destination)

                                if last_action == "cut":
                                    os.remove(source_path)

                                undo_stack.append(
                                    {
                                        "action": last_action,
                                        "src": source_path,
                                        "dst": destination,
                                    }
                                )

                                redo_stack.clear()
                                indicator = "Z"
                                show_error = False
                            except Exception as e:
                                log_error(e)
                                error_message = ("Error: Unable to overwrite the file or directory.")
                                show_error = True
                        elif user_input == ord("k"):
                            base_name, extension = os.path.splitext(os.path.basename(source_path))
                            destination = os.path.join(current_directory, f"{base_name}-copy{extension}")

                            counter = 1
                            while os.path.exists(destination):
                                new_name = f"{base_name}-copy ({counter}){extension}"
                                destination = os.path.join(current_directory, new_name)
                                counter += 1

                            try:
                                if os.path.isdir(source_path):
                                    shutil.copytree(source_path, destination)
                                else:
                                    shutil.copy2(source_path, destination)

                                undo_stack.append({"action": "copy", "src": source_path, "dst": destination,})
                                redo_stack.clear()
                                indicator = "Z"
                                show_error = False
                            except Exception as e:
                                log_error(e)
                                error_message = ("Error: Unable to copy. Check logs for details.")
                                show_error = True
                        elif user_input == ord("c"):
                            show_error = False
                            continue
                    else:
                        try:
                            if last_action == "cut":
                                shutil.move(source_path, destination)
                            else:
                                if os.path.isdir(source_path):
                                    shutil.copytree(source_path, destination)
                                else:
                                    shutil.copy2(source_path, destination)

                            undo_stack.append({"action": last_action, "src": source_path, "dst": destination,})
                            redo_stack.clear()
                            indicator = "Z"
                            show_error = False
                        except Exception as e:
                            log_error(e)
                            error_message = ("Error: Unable to move or copy the file or directory.")
                            show_error = True
        elif key == curses.KEY_F2:
            if files:
                selected_item = files[current_index]
                selected_path = os.path.join(current_directory, selected_item)
                stdscr.move(max_height - 1, 0)
                stdscr.clrtoeol()
                stdscr.addstr(max_height - 1, 0, "Rename to: ", curses.A_BOLD)
                stdscr.refresh()
                curses.echo()
                curses.curs_set(1)
                try:
                    new_name = (
                        stdscr.getstr(
                            max_height - 1,
                            len("Rename to: "),
                            max_width - len("Rename to: "),
                        )
                        .decode("utf-8")
                        .strip()
                    )
                except Exception as e:
                    log_error(e)
                    curses.noecho()
                    curses.curs_set(0)
                    error_message = ("Error: Unable to retrieve the new name. Please try again.")
                    show_error = True
                    return
                curses.noecho()
                curses.curs_set(0)
                if new_name:
                    new_path = os.path.join(current_directory, new_name)
                    try:
                        os.rename(selected_path, new_path)
                        files[current_index] = new_name
                        undo_stack.append({"action": "rename", "src": selected_path, "dst": new_path})
                        redo_stack.clear()
                        indicator = "Z"
                    except FileExistsError:
                        error_message = ("Error: File or folder with that name already exists.")
                        show_error = True
                    except PermissionError:
                        error_message = "Error: Insufficient permissions to rename the file or folder."
                        show_error = True
                    except OSError:
                        error_message = ("Error: Invalid or restricted name. Please try again.")
                        show_error = True
                    except Exception as e:
                        log_error(e)
                        error_message = ("Error: Unexpected issue occurred. Check logs for details.")
                        show_error = True
                else:
                    error_message = "Error: New name cannot be empty. Please try again."
                    show_error = True

                stdscr.move(max_height - 1, 0)
                stdscr.clrtoeol()
        elif key == ord("z"):
            if undo_stack:
                last_action = undo_stack.pop()
                try:
                    action_type = last_action["action"]
                    src = last_action["src"]
                    dst = last_action["dst"]
                    if action_type == "rename":
                        if os.path.exists(dst):
                            os.rename(dst, src)
                            redo_stack.append({"action": "rename", "src": src, "dst": dst})
                        else:
                            error_message = ("Error: Destination file or directory not found.")
                            show_error = True
                    elif action_type == "copy":
                        if os.path.abspath(src) == os.path.abspath(dst):
                            redo_stack.append({"action": "copy", "src": src, "dst": dst})
                        elif os.path.exists(dst):
                            if os.path.isdir(dst):
                                shutil.rmtree(dst)
                            else:
                                os.remove(dst)
                            redo_stack.append({"action": "copy", "src": src, "dst": dst})
                        else:
                            error_message = ("Error: Destination file or directory not found.")
                            show_error = True
                    elif action_type == "cut":
                        if os.path.exists(dst):
                            os.rename(dst, src)
                            redo_stack.append({"action": "cut", "src": src, "dst": dst})
                        else:
                            error_message = ("Error: Destination file or directory not found.")
                            show_error = True
                    indicator = "Y"
                    show_error = False
                except Exception as e:
                    log_error(e)
                    error_message = (f"Unable to undo the last operation. Check logs for details.")
                    show_error = True
            else:
                show_error = False
                continue
        elif key == ord("y"):
            if redo_stack:
                last_action = redo_stack.pop()
                try:
                    action_type = last_action["action"]
                    src = last_action["src"]
                    dst = last_action["dst"]
                    if action_type == "rename":
                        if os.path.exists(src):
                            os.rename(src, dst)
                            undo_stack.append({"action": "rename", "src": src, "dst": dst})
                        else:
                            error_message = "Error: Source file or folder not found."
                            show_error = True
                    elif action_type == "copy":
                        if not os.path.exists(dst):
                            try:
                                if os.path.isdir(src):
                                    shutil.copytree(src, dst)
                                else:
                                    shutil.copy2(src, dst)
                                undo_stack.append({"action": "copy", "src": src, "dst": dst})
                            except Exception as e:
                                log_error(e)
                                error_message = "Error: Unable to redo copy operation. Check logs for details."
                                show_error = True
                        else:
                            error_message = ("Error: Destination already exists for redo copy.")
                            show_error = True
                    elif action_type == "cut":
                        if os.path.exists(src):
                            try:
                                shutil.move(src, dst)
                                undo_stack.append({"action": "cut", "src": src, "dst": dst})
                            except Exception as e:
                                log_error(e)
                                error_message = "Error: Unable to redo cut operation. Check logs for details."
                                show_error = True
                        else:
                            error_message = "Error: Source file or folder not found."
                            show_error = True
                    indicator = "Z"
                    show_error = False
                except Exception as e:
                    log_error(e)
                    error_message = ("Unable to redo the last operation. Check logs for details.")
                    show_error = True
            else:
                show_error = False
                continue
        elif key == ord("n"):
            show_error = False
            stdscr.addstr(max_height - 1, 0, "Enter new file name: ", curses.A_BOLD)
            stdscr.refresh()
            stdscr.clrtoeol()
            curses.echo()
            curses.curs_set(1)
            new_file = stdscr.getstr(
                max_height - 1,
                len("Enter new file name: "),
                max_width - len("Enter new file name: "),
            )
            curses.noecho()
            curses.curs_set(0)
            new_file = new_file.decode("utf-8")

            if new_file:
                new_file_path = os.path.join(current_directory, new_file)

                try:
                    with open(new_file_path, "w") as f:
                        f.write("")
                    files.append(new_file)
                except PermissionError:
                    error_message = "Error: Insufficient permissions to create file."
                    show_error = True
                except Exception as e:
                    log_error(e)
                    error_message = f"Unexpected error: {str(e)}"
                    show_error = True
        elif key == ord("N"):
            show_error = False
            stdscr.addstr(max_height - 1, 0, "Enter new directory name: ", curses.A_BOLD)
            stdscr.refresh()
            stdscr.clrtoeol()
            curses.echo()
            curses.curs_set(1)
            new_dir = stdscr.getstr(
                max_height - 1,
                len("Enter new directory name: "),
                max_width - len("Enter new directory name: "),
            )
            curses.noecho()
            curses.curs_set(0)
            new_dir = new_dir.decode("utf-8")
            if new_dir:
                new_dir_path = os.path.join(current_directory, new_dir)
                try:
                    os.makedirs(new_dir_path)
                    files.append(new_dir)
                except FileExistsError:
                    error_message = "Error: Directory already exists."
                    show_error = True
                except PermissionError:
                    error_message = ("Error: Insufficient permissions to create directory.")
                    show_error = True
                except Exception as e:
                    log_error(e)
                    error_message = f"Unexpected error: {str(e)}"
                    show_error = True
        elif key == ord("f"):
            show_error = False
            stdscr.addstr(max_height - 1, 0, "Enter search query: ", curses.color_pair(4) | curses.A_BOLD)
            stdscr.refresh()
            stdscr.clrtoeol()
            curses.echo()
            curses.curs_set(1)
            search_query = stdscr.getstr(
                max_height - 1,
                len("Enter search query: "),
                max_width - len("Enter search query: "),
            )
            curses.noecho()
            curses.curs_set(0)
            search_query = search_query.decode("utf-8").lower().strip()

            if search_query:
                matched_files = []
                for root, dirs, files in os.walk(current_directory):
                    for file_name in files + dirs:
                        if all(part.lower() in file_name.lower() for part in search_query.split()):
                            matched_files.append(os.path.join(root, file_name))

                if matched_files:
                    files = [
                        os.path.relpath(path, start=current_directory) for path in matched_files
                    ]
                    current_index = 0
                    indicator = "_"

                    while True:
                        stdscr.clear()
                        stdscr.addstr(0, 0, f"Search Results for '{search_query}':")

                        if files:
                            display_files(stdscr, files, current_index, max_height - 2, current_directory)
                        else:
                            stdscr.addstr(1, 0, "No results found.", curses.A_BOLD)

                        stdscr.refresh()
                        search_key = stdscr.getch()

                        if search_key == 27:
                            break
                        elif search_key == curses.KEY_DOWN:
                            current_index = ((current_index + 1) % len(files) if files else 0)
                        elif search_key == curses.KEY_UP:
                            current_index = ((current_index - 1) % len(files) if files else 0)
                        elif search_key == curses.KEY_RIGHT or search_key == ord("\n"):
                            selected_path = os.path.join(current_directory, files[current_index])
                            if os.path.isdir(selected_path):
                                current_directory = selected_path
                            else:
                                current_directory = os.path.dirname(selected_path)
                                current_index = list_files(current_directory)[0].index(
                                    os.path.basename(selected_path)
                                )
                            break
        elif key == ord(" "):
            selected_item = files[current_index]
            selected_path = os.path.join(current_directory, selected_item)

            if os.path.isfile(selected_path):
                try:
                    with open(selected_path, "r", encoding="utf-8") as f:
                        file_content = f.readlines()

                    preview_index = 0
                    scroll_x = 0

                    while True:
                        stdscr.clear()
                        stdscr.addstr(0, 0, f"Preview: {selected_item} (SPACE to exit, ←/→ & ↑/↓ to scroll)", curses.color_pair(1) | curses.A_BOLD)

                        max_preview_height = max_height - 2
                        for i in range(max_preview_height):
                            if preview_index + i < len(file_content):
                                line = file_content[preview_index + i]
                                stdscr.addstr(i + 1, 0, line[scroll_x : scroll_x + max_width - 1])

                        stdscr.refresh()
                        preview_key = stdscr.getch()

                        if preview_key == ord(" ") or preview_key == 27:
                            break
                        elif (
                            preview_key == curses.KEY_DOWN
                            and preview_index + max_preview_height < len(file_content)
                        ):
                            preview_index += 1
                        elif preview_key == curses.KEY_UP and preview_index > 0:
                            preview_index -= 1
                        elif preview_key == curses.KEY_RIGHT:
                            scroll_x += 5
                        elif preview_key == curses.KEY_LEFT and scroll_x > 0:
                            scroll_x -= 5
                except Exception as e:
                    error_message = f"Error reading file: {str(e)}"
                    show_error = True


if __name__ == "__main__":
    try:
        directories = sys.argv[1].split("*") if len(sys.argv) > 1 else [os.getcwd()]
        for directory in directories:
            validate_directory(directory)
        curses.wrapper(lambda stdscr: main(stdscr, directories))
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        log_error(e)
        print(f"Critical Error: {e}")
        sys.exit(1)

