import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tkinter import font as tkfont
from pygments import highlight
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.formatters import HtmlFormatter
from weasyprint import HTML
import sv_ttk  # For theming
import queue  # For thread-safe communication
import logging

# Configure logging to output to 'codetopdf.log' with debug level
logging.basicConfig(level=logging.DEBUG, filename='codetopdf.log',
                    format='%(asctime)s - %(levelname)s - %(message)s')


class CodebaseConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Codebase to PDF/TXT Converter")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        # Initialize variables
        self.root_dir = None  # Source directory
        self.dest_dir = None  # Destination directory
        self.stop_event = threading.Event()  # Event to signal stopping conversion

        # Initialize queues for thread-safe communication
        self.tree_queue = queue.Queue()
        self.gui_queue = queue.Queue()

        # Apply theme using sv_ttk
        sv_ttk.set_theme("light")  # Options: "light", "dark", etc.

        # Configure fonts
        self.configure_fonts()

        # Create UI components
        self.create_menu()
        self.create_main_frames()
        self.create_treeview()
        self.create_control_widgets()
        self.create_log_area()
        self.create_status_bar()

        # Start processing queues
        self.root.after(100, self.process_tree_queue)
        self.root.after(100, self.process_gui_queue)

    def configure_fonts(self):
        """Configure default and Treeview fonts."""
        self.default_font = tkfont.nametofont("TkDefaultFont")
        self.default_font.configure(size=10)
        self.tree_font = tkfont.Font(family="Segoe UI", size=10)

    def create_menu(self):
        """Create the menu bar with File and Help menus."""
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        # File Menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Select Source Folder", command=self.select_folder)
        file_menu.add_command(label="Restart", command=self.restart_app)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Help Menu
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.about_app)

    def create_main_frames(self):
        """Create main frames for organizing the layout."""
        # Frame for Treeview and Scrollbars
        self.tree_frame = ttk.Frame(self.root)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame for Control Buttons and Stats
        self.control_frame = ttk.Frame(self.root)
        self.control_frame.pack(pady=5, padx=10, fill=tk.X)

        # Sub-frames for better layout
        self.stats_frame = ttk.Frame(self.control_frame)
        self.stats_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.buttons_frame = ttk.Frame(self.control_frame)
        self.buttons_frame.pack(side=tk.RIGHT, fill=tk.X)

    def create_treeview(self):
        """Create the Treeview widget with scrollbars and event bindings."""
        # Create Treeview
        self.tree = ttk.Treeview(self.tree_frame, selectmode='none', show='tree')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add vertical scrollbar
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill='y')
        self.tree.configure(yscrollcommand=vsb.set)

        # Add horizontal scrollbar
        hsb = ttk.Scrollbar(self.root, orient="horizontal", command=self.tree.xview)
        hsb.pack(side=tk.BOTTOM, fill='x')
        self.tree.configure(xscrollcommand=hsb.set)

        # Bind events
        self.tree.bind('<Button-1>', self.on_treeview_click)  # Handle clicks
        self.tree.bind('<<TreeviewOpen>>', self.on_treeview_open)  # Handle node expansion

    def create_control_widgets(self):
        """Create control widgets including stats labels, checkboxes, buttons, and progress bar."""
        # Stats Labels
        self.stats_labels = {}
        self.stats_labels['selected'] = ttk.Label(self.stats_frame, text="Selected Files: 0")
        self.stats_labels['selected'].pack(side=tk.LEFT, padx=10)

        self.stats_labels['success'] = ttk.Label(self.stats_frame, text="Successfully Converted: 0")
        self.stats_labels['success'].pack(side=tk.LEFT, padx=10)

        self.stats_labels['fail'] = ttk.Label(self.stats_frame, text="Failed Conversions: 0")
        self.stats_labels['fail'].pack(side=tk.LEFT, padx=10)

        # Output Format Selection
        self.format_frame = ttk.Frame(self.control_frame)
        self.format_frame.pack(side=tk.LEFT, padx=10)

        self.pdf_var = tk.BooleanVar(value=True)  # PDF conversion enabled by default
        self.txt_var = tk.BooleanVar(value=False)  # TXT conversion disabled by default

        self.pdf_checkbox = ttk.Checkbutton(self.format_frame, text="PDF", variable=self.pdf_var)
        self.pdf_checkbox.pack(side=tk.LEFT, padx=5)

        self.txt_checkbox = ttk.Checkbutton(self.format_frame, text="TXT", variable=self.txt_var)
        self.txt_checkbox.pack(side=tk.LEFT, padx=5)

        # Buttons
        self.select_button = ttk.Button(self.buttons_frame, text="Select Source Folder",
                                        command=self.select_folder)
        self.select_button.pack(side=tk.LEFT, padx=5)

        self.lock_button = ttk.Button(self.buttons_frame, text="Lock Selection",
                                      command=self.lock_selection)
        self.lock_button.pack(side=tk.LEFT, padx=5)
        self.lock_button.config(state=tk.DISABLED)  # Initially disabled

        self.start_button = ttk.Button(self.buttons_frame, text="Start Conversion",
                                       command=self.on_start_conversion)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.start_button.config(state=tk.DISABLED)  # Initially disabled

        self.stop_button = ttk.Button(self.buttons_frame, text="Stop Conversion",
                                      command=self.stop_conversion)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.config(state=tk.DISABLED)  # Initially disabled

        # Progress Bar
        self.progress_frame = ttk.Frame(self.control_frame)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self.progress_bar = ttk.Progressbar(self.progress_frame, orient='horizontal', mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True)

    def create_log_area(self):
        """Create the log area to display conversion logs."""
        self.log_frame = ttk.LabelFrame(self.root, text="Conversion Log")
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.log_area = tk.Text(self.log_frame, wrap=tk.WORD, height=10, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def create_status_bar(self):
        """Create the status bar at the bottom of the window."""
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def about_app(self):
        """Display information about the application."""
        messagebox.showinfo("About",
                            "Codebase to PDF/TXT Converter\nVersion 1.0\nDeveloped by [Your Name]")

    def select_folder(self):
        """Handle the selection of the source folder."""
        selected_dir = filedialog.askdirectory(title="Select Source Code Folder")
        if selected_dir:
            # Reset previous state
            self.reset_state()

            self.root_dir = selected_dir
            self.lock_button.config(state=tk.NORMAL)
            self.select_button.config(state=tk.DISABLED)

            # Populate the Treeview with the root node
            self.populate_treeview()

    def populate_treeview(self):
        """Populate the Treeview with the root directory."""
        # Clear existing Treeview
        self.tree.delete(*self.tree.get_children())

        root_name = os.path.basename(self.root_dir)
        if not root_name:
            root_name = self.root_dir  # Handle case when selecting root directory

        # Insert root node with a dummy child for lazy loading
        root_node = self.tree.insert('', 'end', text=f"☐ {root_name}", values=[self.root_dir], tags=('unchecked',))
        self.tree.insert(root_node, 'end', text='Loading...', values=[''], tags=('dummy',))

        logging.debug(f"Populated Treeview with root node: {self.root_dir}")

    def on_treeview_open(self, event):
        """Handle the expansion of a Treeview node."""
        node = self.tree.focus()
        children = self.tree.get_children(node)
        if len(children) == 1 and 'dummy' in self.tree.item(children[0], 'tags'):
            # Remove dummy
            self.tree.delete(children[0])

            # Get absolute path
            abspath = self.tree.item(node, 'values')[0]

            # Log the expansion attempt
            logging.debug(f"Expanding node: {abspath}")

            # Start a background thread to scan and enqueue children
            try:
                threading.Thread(target=self.scan_and_enqueue_children,
                                 args=(abspath, node),
                                 daemon=True).start()
            except Exception as e:
                logging.error(f"Error starting scan thread: {e}")
                self.gui_queue.put(('log', f"Error starting scan thread: {e}\n"))

    def on_treeview_click(self, event):
        """
        Handle clicks in the Treeview.
        Distinguish between clicks on the expand arrow and the checkbox.
        """
        # Detect if the click was on the 'tree' region
        region = self.tree.identify("region", event.x, event.y)
        if region != "tree":
            return

        # Get the element that was clicked
        element = self.tree.identify_element(event.x, event.y)
        if element != "text":
            return  # Click was not on the text (checkbox)

        item = self.tree.identify_row(event.y)
        if not item:
            return

        # Get the current text
        current_text = self.tree.item(item, 'text')
        if current_text.startswith("☐ "):
            new_state = "☑ "
            new_tag = 'checked'
        elif current_text.startswith("☑ "):
            new_state = "☐ "
            new_tag = 'unchecked'
        elif current_text.startswith("☒ "):
            new_state = "☑ "
            new_tag = 'checked'
        else:
            return  # Not a checkbox item

        # Update the text
        self.tree.item(item, text=new_state + current_text[2:])

        # Update the tags
        self.tree.item(item, tags=(new_tag,))

        # Log the checkbox state change
        logging.debug(f"Checkbox toggled: {current_text} -> {new_state + current_text[2:]} for item {item}")

        # Update children and parents accordingly
        self.update_children(item, new_tag)
        self.update_parent_check(item)

    def update_children(self, parent, new_tag):
        """
        Recursively update the checkbox state of all child items.
        """
        for child in self.tree.get_children(parent):
            # Update checkbox state
            text = self.tree.item(child, 'text')
            if text.startswith("☐ ") or text.startswith("☑ ") or text.startswith("☒ "):
                current_text = self.tree.item(child, 'text')
                if new_tag == 'checked':
                    new_text = "☑ " + current_text[2:]
                elif new_tag == 'unchecked':
                    new_text = "☐ " + current_text[2:]
                self.tree.item(child, text=new_text)
                self.tree.item(child, tags=(new_tag,))

                # Log the recursive update
                logging.debug(f"Updating child {child}: {current_text} -> {new_text}")

                # Recursive update for subchildren
                self.update_children(child, new_tag)

    def update_parent_check(self, child):
        """
        Recursively update the checkbox state of parent items based on their children's states.
        """
        parent = self.tree.parent(child)
        if not parent:
            return

        children = self.tree.get_children(parent)
        checked = 0
        unchecked = 0
        for c in children:
            text = self.tree.item(c, 'text')
            if text.startswith("☑ ") or text.startswith("☒ "):
                checked += 1
            elif text.startswith("☐ "):
                unchecked += 1

        if checked == len(children):
            new_state = "☑ "
            new_tag = 'checked'
        elif unchecked == len(children):
            new_state = "☐ "
            new_tag = 'unchecked'
        else:
            new_state = "☒ "
            new_tag = 'partial'

        current_text = self.tree.item(parent, 'text')
        new_text = new_state + current_text[2:]
        self.tree.item(parent, text=new_text)
        self.tree.item(parent, tags=(new_tag,))

        # Log the parent update
        logging.debug(f"Updating parent {parent}: {current_text} -> {new_text}")

        # Recursive update for higher-level parents
        self.update_parent_check(parent)

    def get_checked_items(self):
        """
        Retrieve all checked files only.
        Ignore the checked state of directories.
        """
        checked_items = []

        def recurse(item):
            tags = self.tree.item(item, 'tags')
            values = self.tree.item(item, 'values')
            if not values or len(values) < 1:
                return
            abspath = values[0]
            if 'checked' in tags and os.path.isfile(abspath):
                if not abspath.endswith('.pdf'):  # Exclude already converted PDFs
                    checked_items.append(abspath)
            # Recurse into children regardless of parent check state
            for child in self.tree.get_children(item):
                recurse(child)

        for child in self.tree.get_children():
            recurse(child)
        return checked_items

    def lock_selection(self):
        """Lock the current selection to prevent further changes and enable conversion."""
        selected_items = self.get_checked_items()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select at least one file or folder before locking selection.")
            return

        # Update selected files count
        total_selected_files = len(selected_items)
        self.stats_labels['selected'].config(text=f"Selected Files: {total_selected_files}")

        # Disable selection changes
        self.lock_button.config(state=tk.DISABLED)
        self.select_button.config(state=tk.DISABLED)
        self.tree.unbind('<Button-1>')  # Prevent further checkbox toggling

        # Enable start button
        self.start_button.config(state=tk.NORMAL)

        messagebox.showinfo("Selection Locked", "Your selection has been locked. You can now start the conversion.")

    def on_start_conversion(self):
        """Initiate the conversion process in a separate thread."""
        selected_items = self.get_checked_items()
        if not selected_items:
            messagebox.showwarning("No Selection", "No files or folders selected for conversion.")
            return

        # Confirm conversion
        confirm = messagebox.askyesno("Confirm Conversion",
                                      f"Do you want to start the conversion of {len(selected_items)} files?")
        if not confirm:
            return

        # Select destination folder
        dest_dir = filedialog.askdirectory(title="Select Destination Folder")
        if not dest_dir:
            return

        # Update destination directory
        self.dest_dir = dest_dir

        # Disable buttons during conversion
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.lock_button.config(state=tk.DISABLED)
        self.select_button.config(state=tk.DISABLED)

        # Clear previous logs and reset stats
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')
        self.stats_labels['success'].config(text="Successfully Converted: 0")
        self.stats_labels['fail'].config(text="Failed Conversions: 0")
        self.progress_bar['maximum'] = len(selected_items)
        self.progress_bar['value'] = 0

        # Clear stop event
        self.stop_event.clear()

        # Start conversion in a separate thread
        conversion_thread = threading.Thread(target=self.run_conversion,
                                             args=(selected_items, dest_dir),
                                             daemon=True)
        conversion_thread.start()

    def run_conversion(self, selected_items, dest_dir):
        """
        Convert selected files to PDF and/or TXT formats.
        Runs in a separate thread to keep the GUI responsive.
        """
        success_count = 0
        fail_count = 0
        total_files = len(selected_items)

        for idx, source_file in enumerate(selected_items, 1):
            if self.stop_event.is_set():
                self.gui_queue.put(('log', "Conversion stopped by user.\n"))
                break

            if os.path.isdir(source_file):
                continue  # Skip directories

            # Determine output formats
            formats = []
            if self.pdf_var.get():
                formats.append('pdf')
            if self.txt_var.get():
                formats.append('txt')

            if not formats:
                formats.append('pdf')  # Default to PDF if no selection

            if 'pdf' in formats:
                try:
                    relative_path = os.path.relpath(source_file, self.root_dir)
                    dest_pdf = os.path.join(dest_dir, os.path.splitext(relative_path)[0] + '.pdf')
                    dest_pdf_dir = os.path.dirname(dest_pdf)
                    os.makedirs(dest_pdf_dir, exist_ok=True)  # Create directories if they don't exist
                    self.convert_code_to_pdf(source_file, dest_pdf)
                    success_count += 1
                    self.gui_queue.put(('success', success_count))
                    self.gui_queue.put(('log', f"Converted to PDF: {dest_pdf}\n"))
                except Exception as e:
                    fail_count += 1
                    self.gui_queue.put(('fail', fail_count))
                    self.gui_queue.put(('log', f"Failed to convert {source_file} to PDF: {e}\n"))

            if 'txt' in formats:
                try:
                    relative_path = os.path.relpath(source_file, self.root_dir)
                    dest_txt = os.path.join(dest_dir, os.path.splitext(relative_path)[0] + '.txt')
                    dest_txt_dir = os.path.dirname(dest_txt)
                    os.makedirs(dest_txt_dir, exist_ok=True)  # Create directories if they don't exist
                    with open(source_file, 'r', encoding='utf-8') as f_src, open(dest_txt, 'w', encoding='utf-8') as f_dest:
                        f_dest.write(f_src.read())
                    success_count += 1
                    self.gui_queue.put(('success', success_count))
                    self.gui_queue.put(('log', f"Converted to TXT: {dest_txt}\n"))
                except UnicodeDecodeError as e:
                    fail_count += 1
                    self.gui_queue.put(('fail', fail_count))
                    self.gui_queue.put(('log', f"Failed to convert {source_file} to TXT (Unicode Decode Error): {e}\n"))
                except Exception as e:
                    fail_count += 1
                    self.gui_queue.put(('fail', fail_count))
                    self.gui_queue.put(('log', f"Failed to convert {source_file} to TXT: {e}\n"))

            # Update progress bar
            self.gui_queue.put(('progress', 1))

        # Final messages and button states
        if not self.stop_event.is_set():
            self.gui_queue.put(('message', "All files have been converted.", "info"))

        # Re-enable buttons
        self.gui_queue.put(('buttons', 'enable'))

    def stop_conversion(self):
        """Signal the conversion thread to stop."""
        self.stop_event.set()
        self.stop_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.lock_button.config(state=tk.DISABLED)
        self.select_button.config(state=tk.NORMAL)
        self.gui_queue.put(('log', "The conversion process has been stopped by the user.\n"))

    def process_tree_queue(self):
        """
        Process items from the tree_queue and insert them into the Treeview.
        Runs periodically using the Tkinter 'after' method.
        """
        try:
            while True:
                item = self.tree_queue.get_nowait()
                if item[0] == 'directory':
                    _, dirpath, _, parent = item
                    # Insert directory with a dummy child
                    node = self.tree.insert(parent, 'end', text=f"☐ {os.path.basename(dirpath)}",
                                            values=[dirpath], tags=('unchecked',))
                    self.tree.insert(node, 'end', text='Loading...', values=[''], tags=('dummy',))
                    logging.debug(f"Inserted directory node: {dirpath}")
                elif item[0] == 'file':
                    _, filepath, _, parent = item
                    # Insert file without children
                    self.tree.insert(parent, 'end', text=f"☐ {os.path.basename(filepath)}",
                                    values=[filepath], tags=('unchecked',))
                    logging.debug(f"Inserted file node: {filepath}")
        except queue.Empty:
            pass
        except Exception as e:
            logging.error(f"Error processing tree queue: {e}")
            self.gui_queue.put(('log', f"Error processing tree queue: {e}\n"))
        self.root.after(100, self.process_tree_queue)  # Adjust the delay as needed

    def process_gui_queue(self):
        """
        Process tasks from the gui_queue and update the GUI accordingly.
        Runs periodically using the Tkinter 'after' method.
        """
        try:
            while True:
                task = self.gui_queue.get_nowait()
                if task[0] == 'success':
                    self.stats_labels['success'].config(text=f"Successfully Converted: {task[1]}")
                elif task[0] == 'fail':
                    self.stats_labels['fail'].config(text=f"Failed Conversions: {task[1]}")
                elif task[0] == 'log':
                    self.log_area.config(state='normal')
                    self.log_area.insert(tk.END, task[1])
                    self.log_area.see(tk.END)
                    self.log_area.config(state='disabled')
                elif task[0] == 'progress':
                    self.progress_bar.step(task[1])
                elif task[0] == 'message':
                    messagebox.showinfo("Conversion Status", task[1])
                elif task[0] == 'buttons':
                    if task[1] == 'enable':
                        self.start_button.config(state=tk.DISABLED)
                        self.stop_button.config(state=tk.DISABLED)
                        self.select_button.config(state=tk.NORMAL)
        except queue.Empty:
            pass
        except Exception as e:
            logging.error(f"Error processing GUI queue: {e}")
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, f"Error processing GUI queue: {e}\n")
            self.log_area.config(state='disabled')
        self.root.after(100, self.process_gui_queue)

    def scan_and_enqueue_children(self, abspath, parent_node):
        """
        Scan a directory and enqueue its subdirectories and all files.
        Runs in a separate thread.
        """
        enqueued = False  # Flag to check if any items are enqueued
        try:
            with os.scandir(abspath) as it:
                entries = sorted(it, key=lambda e: e.name.lower())
                for entry in entries:
                    if self.stop_event.is_set():
                        logging.debug(f"Scanning stopped for: {abspath}")
                        break
                    entry_path = entry.path
                    if entry.is_dir(follow_symlinks=False):
                        # Enqueue directory
                        self.tree_queue.put(('directory', entry_path, None, parent_node))
                        logging.debug(f"Enqueued directory: {entry_path}")
                        enqueued = True
                    elif entry.is_file(follow_symlinks=False):
                        # Enqueue file without filtering
                        self.tree_queue.put(('file', entry_path, None, parent_node))
                        logging.debug(f"Enqueued file: {entry_path}")
                        enqueued = True
        except PermissionError as e:
            logging.error(f"Permission denied: {abspath} - {e}")
            self.gui_queue.put(('log', f"Permission denied: {abspath}\n"))
        except Exception as e:
            logging.error(f"Error scanning {abspath}: {e}")
            self.gui_queue.put(('log', f"Error scanning {abspath}: {e}\n"))

        if not enqueued:
            # No eligible files or directories found
            self.gui_queue.put(('log', f"No eligible files or directories found in: {abspath}\n"))

    def reset_state(self):
        """Reset the application state to its initial configuration."""
        # Reset Treeview
        self.tree.delete(*self.tree.get_children())

        # Reset stats
        self.stats_labels['selected'].config(text="Selected Files: 0")
        self.stats_labels['success'].config(text="Successfully Converted: 0")
        self.stats_labels['fail'].config(text="Failed Conversions: 0")

        # Reset buttons
        self.lock_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.select_button.config(state=tk.NORMAL)

        # Clear log area
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')

        # Reset progress bar
        self.progress_bar['maximum'] = 0
        self.progress_bar['value'] = 0

        # Re-bind Treeview clicks
        self.tree.bind('<Button-1>', self.on_treeview_click)

        # Reset root_dir
        self.root_dir = None

        logging.debug("Application state has been reset.")

    def convert_code_to_pdf(self, source_file, dest_file):
        """
        Convert a source code file to a PDF with syntax highlighting.
        Uses Pygments for highlighting and WeasyPrint for PDF generation.
        """
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            raise Exception(f"Failed to read {source_file}: {e}")

        try:
            lexer = get_lexer_for_filename(source_file, stripall=True)
        except Exception:
            # Use a plain text lexer if no specific lexer is found
            lexer = TextLexer(stripall=True)

        # Custom CSS for line wrapping and page margins
        custom_css = '''
        @page {
            size: A4;
            margin: 1cm;
        }
        pre, code {
            white-space: pre-wrap;       /* Wrap long lines */
            word-wrap: break-word;       /* Break words if necessary */
            word-break: break-all;       /* Break long words/chunks */
        }
        '''

        formatter = HtmlFormatter(full=True, style='colorful', cssstyles=custom_css)
        highlighted_code = highlight(code, lexer, formatter)

        # Convert the highlighted HTML to PDF
        try:
            HTML(string=highlighted_code).write_pdf(dest_file)
            logging.debug(f"Successfully converted {source_file} to {dest_file}")
        except Exception as e:
            raise Exception(f"Failed to write PDF {dest_file}: {e}")


    def restart_app(self):
        """Restart the application by resetting its state."""
        confirm = messagebox.askyesno("Restart", "Are you sure you want to restart? All current selections and logs will be cleared.")
        if confirm:
            self.reset_state()
            messagebox.showinfo("Restart", "The application has been restarted. Please select a new source folder.")


def is_text_file(file_path):
    """
    Check if a file is a text file based on MIME type or file extension.
    Includes all code file types.
    """
    import mimetypes
    mime, _ = mimetypes.guess_type(file_path)
    if mime is not None:
        return mime.startswith('text')
    else:
        # Fallback: Check for common text and code file extensions
        text_extensions = [
            '.py', '.txt', '.md', '.java', '.c', '.cpp', '.js', '.html', '.css',
            '.json', '.xml', '.sh', '.bat', '.ini', '.rb', '.go', '.rs', '.swift',
            '.kt', '.ts', '.php', '.pl', '.scala', '.hs', '.lua', '.r', '.sql'
        ]
        return os.path.splitext(file_path)[1].lower() in text_extensions
    
def main():
    """Initialize and run the application."""
    root = tk.Tk()
    app = CodebaseConverterApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
