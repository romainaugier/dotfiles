####################################################
# GDB Enhanced UI - A single-file GDB prettifier   #
# Installation:                                    #
#     Add to ~/.gdbinit: source /path/to/gdbui.py  #
#     Or load manually in GDB: source gdbui.py     #
####################################################

import gdb
import re
import sys
import os

# ============================================================================
# Color Definitions
# ============================================================================

class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[91m'           # Bright red for modified
    GREEN = '\033[92m'         # Bright green
    YELLOW = '\033[93m'        # Bright yellow
    BLUE = '\033[94m'          # Bright blue
    MAGENTA = '\033[95m'       # Bright magenta
    CYAN = '\033[96m'          # Bright cyan
    WHITE = '\033[97m'         # Bright white
    GRAY = '\033[90m'          # Bright black (gray)

    # Specific semantic colors
    REGISTER_NAME = '\033[32m'      # Green for register names
    REGISTER_CHANGED = '\033[91m'    # Bright red for changed values
    ADDRESS = '\033[96m'             # Cyan for addresses
    COMMENT = '\033[90m'             # Gray for comments/annotations
    ARROW = '\033[90m'               # Gray for arrows
    CURRENT_LINE = '\033[92m'        # Bright green for current line marker
    STRING = '\033[93m'              # Yellow for strings

# ============================================================================
# Terminal Utilities
# ============================================================================

def get_terminal_size():
    """Get terminal size (width, height)"""
    try:
        size = os.get_terminal_size()
        return size.columns, size.lines
    except:
        # Fallback method
        try:
            import subprocess
            output = subprocess.check_output(['stty', 'size'], stderr=subprocess.DEVNULL)
            rows, cols = output.decode().strip().split()
            return int(cols), int(rows)
        except:
            return 120, 40  # Default fallback

def colorize(text, color):
    """Apply color to text"""
    return f"{color}{text}{Colors.RESET}"

def print_separator(char='─', label='', color=Colors.CYAN, width=None):
    """Print a separator line with optional label"""
    if width is None:
        width, _ = get_terminal_size()

    if label:
        label_text = f" {label} "
        remaining = width - len(label_text)
        left = remaining // 2
        right = remaining - left
        line = char * left + label_text + char * right
    else:
        line = char * width
    print(colorize(line, color))

def format_address(addr):
    """Format address with color"""
    if addr is None or addr == 0:
        return colorize("0x0", Colors.GRAY)

    # Determine if it's a 32-bit or 64-bit address
    if addr > 0xFFFFFFFF:
        addr_str = f"0x{addr:016x}"
    else:
        addr_str = f"0x{addr:08x}"

    return colorize(addr_str, Colors.ADDRESS)

# ============================================================================
# Layout Manager
# ============================================================================

class LayoutManager:
    """Manages the layout and sizing of display sections"""

    def __init__(self):
        self.width, self.height = get_terminal_size()
        self.calculate_sections()

    def calculate_sections(self):
        """Calculate optimal sizes for each section"""
        # Account for every line we'll print
        # Legend: 2 lines (legend text + blank)
        # Each section: 1 separator + content lines
        # Bottom separator: 1 line
        # Prompt/command line: 1 line reserved

        used_lines = 0

        # Legend
        used_lines += 2  # legend + blank line after

        # Registers section
        self.registers_content_lines = 18  # 16 general regs + flags + segment regs
        used_lines += 1 + self.registers_content_lines  # separator + content

        # Stack section
        self.stack_lines = 10
        used_lines += 1 + self.stack_lines  # separator + content

        # Code section - FIXED at 8 disassembly lines max + separator + source (5 lines) + separator
        self.code_disasm_lines = 8
        self.code_source_lines = 5
        self.code_separators = 2  # code separator + source separator
        used_lines += self.code_separators + self.code_disasm_lines + self.code_source_lines

        # Threads section
        self.threads_lines = 3
        used_lines += 1 + self.threads_lines  # separator + content

        # Trace section
        self.trace_lines = 3
        used_lines += 1 + self.trace_lines  # separator + content

        # Bottom separator
        used_lines += 1

        # Calculate padding needed to fill screen (leave 1 line for command prompt)
        self.padding_lines = max(0, self.height - used_lines - 1)

    def refresh(self):
        """Refresh terminal size"""
        self.width, self.height = get_terminal_size()
        self.calculate_sections()

# ============================================================================
# Register Display
# ============================================================================

class RegisterDisplay:
    """Display CPU registers in a formatted manner"""

    # Register groups for x86-64
    GENERAL_REGS = ['rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp',
                    'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15']

    def __init__(self):
        self.prev_values = {}

    def get_register_value(self, reg_name):
        """Get the value of a register"""
        try:
            val = gdb.parse_and_eval(f"${reg_name}")
            return int(val)
        except:
            return None

    def get_pointer_info(self, addr):
        """Try to get information about what an address points to"""
        if addr == 0:
            return ""

        try:
            # Try to read as pointer
            val = gdb.parse_and_eval(f"*(long*)0x{addr:x}")
            val_int = int(val)
            return format_address(val_int)
        except:
            pass

        try:
            # Try to get symbol
            sym_info = gdb.execute(f"info symbol 0x{addr:x}", to_string=True).strip()
            if 'No symbol' not in sym_info and sym_info:
                # Clean up symbol info
                sym_info = sym_info.split('\n')[0]
                if len(sym_info) > 40:
                    sym_info = sym_info[:37] + "..."
                return colorize(sym_info, Colors.COMMENT)
        except:
            pass

        return ""

    def format_register_line(self, reg_name, value):
        """Format a single register line"""
        # Check if value changed
        changed = reg_name in self.prev_values and self.prev_values.get(reg_name) != value

        # Format register name
        if changed:
            reg_label = colorize(f"${reg_name:<4s}", Colors.REGISTER_CHANGED)
        else:
            reg_label = colorize(f"${reg_name:<4s}", Colors.REGISTER_NAME)

        # Format value
        if value is None:
            val_str = colorize("0x0", Colors.GRAY)
        else:
            if changed:
                val_str = colorize(f"0x{value:016x}" if value > 0xFFFFFFFF else f"0x{value:08x}",
                                 Colors.REGISTER_CHANGED)
            else:
                val_str = format_address(value)

        # Build the line
        result = f"{reg_label} : {val_str}"

        # Add annotation for special registers
        annotation = ""
        if value and value != 0:
            if reg_name in ['rsp', 'rbp', 'rsi', 'rdi']:
                annotation = self.get_pointer_info(value)
            elif reg_name == 'rip':
                try:
                    # Try to get function name
                    frame = gdb.selected_frame()
                    func = frame.function()
                    if func:
                        annotation = colorize(f"<{func.name}>", Colors.COMMENT)
                except:
                    pass

        if annotation:
            arrow = colorize(" → ", Colors.ARROW)
            result += f"{arrow}{annotation}"

        # Update previous values
        self.prev_values[reg_name] = value

        return result

    def parse_eflags(self, eflags):
        """Parse eflags register into readable format"""
        flags = []
        flag_bits = [
            (0, 'carry'),
            (2, 'PARITY'),
            (4, 'adjust'),
            (6, 'ZERO'),
            (7, 'sign'),
            (8, 'trap'),
            (9, 'INTERRUPT'),
            (10, 'direction'),
            (11, 'overflow'),
        ]

        for bit, name in flag_bits:
            if eflags & (1 << bit):
                flags.append(name)

        return ' '.join(flags) if flags else 'none'

    def display(self):
        """Display all registers"""
        print_separator(label="registers", color=Colors.CYAN)

        # Display general purpose registers
        for reg in self.GENERAL_REGS:
            val = self.get_register_value(reg)
            print(self.format_register_line(reg, val))

        # Display flags register
        eflags = self.get_register_value('eflags')
        if eflags is not None:
            flags_str = self.parse_eflags(eflags)
            reg_label = colorize("$rflags", Colors.REGISTER_NAME)
            val_str = format_address(eflags)
            arrow = colorize(" → ", Colors.ARROW)
            comment = colorize(f"[{flags_str}]", Colors.COMMENT)
            print(f"{reg_label:10s} : {val_str}{arrow}{comment}")

        # Display segment registers
        seg_parts = []
        for seg in ['cs', 'ss', 'ds', 'es', 'fs', 'gs']:
            val = self.get_register_value(seg)
            if val is not None:
                seg_label = colorize(f"${seg}", Colors.REGISTER_NAME)
                val_str = colorize(f"0x{val:04x}", Colors.ADDRESS)
                seg_parts.append(f"{seg_label}: {val_str}")

        if seg_parts:
            print("  ".join(seg_parts))

# ============================================================================
# Stack Display
# ============================================================================

class StackDisplay:
    """Display stack contents"""

    def display(self, lines=10):
        """Display stack contents"""
        print_separator(label="stack", color=Colors.CYAN)

        try:
            # Get stack pointer
            sp = int(gdb.parse_and_eval("$rsp"))

            # Read stack values
            for i in range(lines):
                addr = sp + (i * 8)
                try:
                    val = gdb.parse_and_eval(f"*(long*)0x{addr:x}")
                    val_int = int(val)

                    # Format components
                    addr_str = format_address(addr)
                    offset_str = colorize(f"+0x{i*8:04x}", Colors.GRAY)
                    val_str = format_address(val_int)

                    # Build line
                    line = f"{addr_str} {offset_str}: {val_str}"

                    # Add annotations
                    annotation = ""
                    if i == 0:
                        annotation = colorize("← $rsp", Colors.COMMENT)
                    else:
                        # Try to resolve symbol
                        try:
                            sym_info = gdb.execute(f"info symbol 0x{val_int:x}", to_string=True).strip()
                            if 'No symbol' not in sym_info and sym_info:
                                sym_info = sym_info.split('\n')[0]
                                if len(sym_info) > 50:
                                    sym_info = sym_info[:47] + "..."
                                arrow = colorize(" → ", Colors.ARROW)
                                annotation = f"{arrow}{colorize(sym_info, Colors.COMMENT)}"
                        except:
                            pass

                    if annotation:
                        line += annotation

                    print(line)
                except:
                    pass
        except:
            print(colorize("  Stack not available", Colors.GRAY))

# ============================================================================
# Code Display
# ============================================================================

class CodeDisplay:
    """Display disassembly and source code"""

    def display(self, disasm_lines=8):
        """Display code around current instruction"""
        print_separator(label="code:i386:x86-64", color=Colors.CYAN)

        lines_printed = 0

        try:
            # Get current program counter
            pc = int(gdb.parse_and_eval("$rip"))

            # First, try to disassemble the entire function to get all lines
            try:
                # Try to get the function bounds
                frame = gdb.selected_frame()
                block = frame.block()
                if block:
                    # Get function start and end
                    while block.function is None and block.superblock is not None:
                        block = block.superblock

                    if block.function:
                        func_start = block.start
                        func_end = block.end
                        disasm = gdb.execute(f"disassemble 0x{func_start:x},0x{func_end:x}", to_string=True)
                    else:
                        raise Exception("No function block")
                else:
                    raise Exception("No block")
            except:
                # Fallback: disassemble around PC
                # Use larger range to ensure we get enough context
                before = disasm_lines * 8  # More bytes before
                after = disasm_lines * 8   # More bytes after
                try:
                    disasm = gdb.execute(f"disassemble $rip-{before},$rip+{after}", to_string=True)
                except:
                    # If that fails, just disassemble forward
                    disasm = gdb.execute(f"disassemble $rip,$rip+{after*2}", to_string=True)

            # Parse all disassembly lines
            all_lines = []
            current_idx = -1

            for line in disasm.split('\n'):
                if line.strip() and not line.startswith('Dump') and not line.startswith('End of'):
                    formatted = self.format_disasm_line(line, pc)
                    if formatted:
                        if '=>' in line:
                            current_idx = len(all_lines)
                        all_lines.append(formatted)

            # Display exactly disasm_lines (8) lines centered around current instruction
            if current_idx >= 0:
                # Calculate window around current instruction
                half = disasm_lines // 2
                start = max(0, current_idx - half)
                end = min(len(all_lines), start + disasm_lines)

                # Adjust start if we're near the end
                if end - start < disasm_lines:
                    start = max(0, end - disasm_lines)

                for line in all_lines[start:end]:
                    print(line)
                    lines_printed += 1
            else:
                # No current instruction marker found, show first N lines
                for line in all_lines[:disasm_lines]:
                    print(line)
                    lines_printed += 1

        except Exception as e:
            print(colorize(f"  Code not available", Colors.GRAY))
            lines_printed += 1

        # Pad with empty lines to reach exactly disasm_lines
        while lines_printed < disasm_lines:
            print()
            lines_printed += 1

        # Try to show source code (returns number of lines printed)
        lines_printed += self.display_source()

    def format_disasm_line(self, line, current_pc):
        """Format a disassembly line with colors"""
        if not line.strip():
            return None

        is_current = '=>' in line

        # Remove => marker
        line = line.replace('=>', '  ')

        # Parse the line (format: "   0x401234 <func+20>:  mov    rax, rdi")
        parts = line.split(':', 1)
        if len(parts) != 2:
            return line

        addr_part = parts[0].strip()
        instr_part = parts[1].strip()

        # Extract address
        addr_match = re.search(r'0x[0-9a-f]+', addr_part)
        if not addr_match:
            return line

        addr = addr_match.group(0)

        # Extract function info if present
        func_match = re.search(r'<([^>]+)>', addr_part)
        func_info = ""
        if func_match:
            func_info = colorize(f" <{func_match.group(1)}>", Colors.COMMENT)

        # Format address
        addr_colored = format_address(int(addr, 16))

        # Format instruction
        instr_formatted = self.colorize_instruction(instr_part)

        # Build the line
        if is_current:
            marker = colorize('→', Colors.CURRENT_LINE)
            result = f"{marker} {addr_colored}{func_info}:  {instr_formatted}"
        else:
            marker = ' '
            result = f"{marker} {addr_colored}{func_info}:  {instr_formatted}"

        return result

    def colorize_instruction(self, instr):
        """Colorize instruction mnemonics and operands"""
        # Split instruction and operands
        parts = instr.split(None, 1)
        if not parts:
            return instr

        mnemonic = parts[0]
        operands = parts[1] if len(parts) > 1 else ""

        # Color mnemonic
        mnemonic_colored = colorize(mnemonic, Colors.YELLOW)

        # Color operands
        if operands:
            # Color addresses
            operands = re.sub(r'(0x[0-9a-f]+)',
                            lambda m: colorize(m.group(1), Colors.ADDRESS),
                            operands)
            # Color registers
            operands = re.sub(r'\b(r[abcd]x|r[sb]p|r[sd]i|r[0-9]+[dwb]?|e[abcd]x|e[sb]p|e[sd]i)\b',
                            lambda m: colorize(m.group(1), Colors.REGISTER_NAME),
                            operands)
            # Color strings
            operands = re.sub(r'"[^"]*"',
                            lambda m: colorize(m.group(0), Colors.STRING),
                            operands)

        return f"{mnemonic_colored}    {operands}" if operands else mnemonic_colored

    def display_source(self):
        """Display source code if available, returns number of lines printed"""
        lines_printed = 0
        try:
            sal = gdb.selected_frame().find_sal()
            if sal.symtab and sal.line > 0:
                filename = sal.symtab.filename
                line_num = sal.line

                # Get just the basename for display
                basename = os.path.basename(filename)
                print_separator(label=f"source:{basename}+{line_num}", color=Colors.CYAN)
                lines_printed += 1

                with open(filename, 'r') as f:
                    lines = f.readlines()

                # Display context (5 lines: 2 before, current, 2 after)
                start = max(0, line_num - 3)
                end = min(len(lines), line_num + 2)

                for i in range(start, end):
                    line_text = lines[i].rstrip()
                    num_str = f"{i+1:5d}"

                    if i + 1 == line_num:
                        # Current line
                        marker = colorize('→', Colors.CURRENT_LINE)
                        num_str = colorize(num_str, Colors.CURRENT_LINE)
                        line_text = colorize(line_text, Colors.WHITE)
                    else:
                        marker = ' '
                        num_str = colorize(num_str, Colors.GRAY)

                    print(f"{marker} {num_str}  {line_text}")
                    lines_printed += 1
        except:
            pass

        return lines_printed

# ============================================================================
# Thread Display
# ============================================================================

class ThreadDisplay:
    """Display thread information"""

    def display(self):
        """Display active threads (compact)"""
        print_separator(label="threads", color=Colors.CYAN)

        try:
            info = gdb.execute("info threads", to_string=True)
            lines = [l for l in info.split('\n') if l.strip()]

            # Show only first 2 threads or all if less
            for line in lines[:3]:
                if line.strip():
                    # Highlight current thread
                    if '*' in line[:5]:
                        print(colorize(line, Colors.CURRENT_LINE))
                    else:
                        print(line)
        except:
            print(colorize("  [#0] Id 1, Name: \"program\", stopped", Colors.WHITE))

# ============================================================================
# Backtrace Display
# ============================================================================

class BacktraceDisplay:
    """Display call stack backtrace"""

    def display(self, limit=2):
        """Display backtrace (compact)"""
        print_separator(label="trace", color=Colors.CYAN)

        try:
            bt = gdb.execute(f"backtrace {limit}", to_string=True)
            lines = [l for l in bt.split('\n') if l.strip()]

            for line in lines[:limit+1]:
                if line.strip():
                    # Color frame numbers
                    line = re.sub(r'(#\d+)', lambda m: colorize(m.group(1), Colors.CYAN), line)
                    # Color addresses
                    line = re.sub(r'(0x[0-9a-f]+)', lambda m: colorize(m.group(1), Colors.ADDRESS), line)
                    # Color function names
                    line = re.sub(r'\bin\s+(\w+)', lambda m: f"in {colorize(m.group(1), Colors.YELLOW)}", line)
                    print(line)
        except:
            try:
                frame = gdb.selected_frame()
                if frame.function():
                    func_name = frame.function().name
                    pc = frame.pc()
                    print(f"{colorize('#0', Colors.CYAN)} {format_address(pc)} → {colorize(f'{func_name}()', Colors.YELLOW)}")
            except:
                print(colorize("  Backtrace not available", Colors.GRAY))

# ============================================================================
# Main Context Display
# ============================================================================

class ContextDisplay:
    """Main context display combining all components"""

    def __init__(self):
        self.layout = LayoutManager()
        self.reg_display = RegisterDisplay()
        self.stack_display = StackDisplay()
        self.code_display = CodeDisplay()
        self.thread_display = ThreadDisplay()
        self.trace_display = BacktraceDisplay()

    def display(self):
        """Display complete context"""
        # Refresh layout to get current terminal size
        self.layout.refresh()

        # Track total lines printed
        lines_printed = 0

        # Don't clear screen, just start fresh
        print()
        lines_printed += 1

        # Display legend at the top
        legend = "[ Legend: "
        legend += colorize("Modified register", Colors.REGISTER_CHANGED) + " | "
        legend += colorize("Code", Colors.YELLOW) + " | "
        legend += colorize("Heap", Colors.GREEN) + " | "
        legend += colorize("Stack", Colors.MAGENTA) + " | "
        legend += colorize("String", Colors.STRING) + " ]"
        print(legend)
        lines_printed += 1

        # Display all sections
        self.reg_display.display()
        lines_printed += 1 + self.layout.registers_content_lines  # separator + content

        self.stack_display.display(lines=self.layout.stack_lines)
        lines_printed += 1 + self.layout.stack_lines  # separator + content

        self.code_display.display(disasm_lines=self.layout.code_disasm_lines)
        lines_printed += self.layout.code_separators + self.layout.code_disasm_lines + self.layout.code_source_lines

        self.thread_display.display()
        lines_printed += 1 + self.layout.threads_lines  # separator + content

        self.trace_display.display()
        lines_printed += 1 + self.layout.trace_lines  # separator + content

        # Print bottom separator
        width, _ = get_terminal_size()
        print(colorize("─" * width, Colors.CYAN))
        lines_printed += 1

        # Fill remaining lines with empty lines to reach bottom of screen
        # Leave 1 line for the command prompt
        for _ in range(self.layout.padding_lines):
            print()

        sys.stdout.flush()

# ============================================================================
# GDB Commands
# ============================================================================

class ContextCommand(gdb.Command):
    """Display enhanced context information"""

    def __init__(self):
        super(ContextCommand, self).__init__("context", gdb.COMMAND_USER)
        self.display = ContextDisplay()

    def invoke(self, arg, from_tty):
        self.display.display()

# Hook into stop events
class ContextStopHandler:
    """Automatically display context when execution stops"""

    def __init__(self):
        self.display = ContextDisplay()
        gdb.events.stop.connect(self.handle_stop)

    def handle_stop(self, event):
        try:
            self.display.display()
        except Exception as e:
            print(colorize(f"Error displaying context: {e}", Colors.RED))

# ============================================================================
# Initialization
# ============================================================================

def init_enhanced_ui():
    """Initialize the enhanced UI"""
    print()
    print(colorize("╔════════════════════════════════════════╗", Colors.CYAN))
    print(colorize("║         GDB Enhanced UI Loaded         ║", Colors.CYAN))
    print(colorize("╚════════════════════════════════════════╝", Colors.CYAN))
    print(colorize("\nCommands:", Colors.YELLOW))
    print(colorize("  context  - Display context manually", Colors.WHITE))
    print(colorize("\nAuto-display is enabled on all stops\n", Colors.GREEN))
    print()

    # Register commands
    ContextCommand()

    # Auto-enable context display
    ContextStopHandler()

# Initialize when loaded
init_enhanced_ui()
