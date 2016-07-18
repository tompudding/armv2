import Tkinter
import random
import messages
import string
import struct
import itertools
import sys
import Queue
import time

def insert_wrapper(func):
    def wrapper(self, *args, **kwargs):
        self.configure(state=Tkinter.NORMAL)
        func(self,*args,**kwargs)
        self.configure(state=Tkinter.DISABLED)
    return wrapper

Tkinter.Text.insert = insert_wrapper(Tkinter.Text.insert)
Tkinter.Text.delete = insert_wrapper(Tkinter.Text.delete)

mode_names = ['USR','FIQ','IRQ','SUP']

class Button(Tkinter.Button):
    unselected_fg = 'lawn green'
    unselected_bg = 'black'
    #Inverted for selected
    selected_fg = unselected_bg
    selected_bg = unselected_fg
    disabled_border = '#004000'

    def __init__(self, parent, text, callback, state=Tkinter.NORMAL):
        self.parent = parent
        self.callback = callback
        border = self.unselected_fg if state == Tkinter.NORMAL else self.disabled_border
        Tkinter.Button.__init__(self,
                                self.parent,
                                width=6,
                                pady=2,
                                highlightbackground=border,
                                highlightcolor=self.unselected_fg,
                                highlightthickness=1,
                                fg=self.unselected_fg,
                                bg=self.unselected_bg,
                                activebackground=self.selected_bg,
                                activeforeground=self.selected_fg,
                                command=self.callback,
                                text=text,
                                relief=Tkinter.SOLID,
                                state=state,
                                )

    def disable(self):
        self.config(state=Tkinter.DISABLED)
        self.config(highlightbackground=self.disabled_border)

    def enable(self):
        self.config(state=Tkinter.NORMAL)
        self.config(highlightbackground=self.unselected_fg)


class View(object):
    unselected_fg = 'lawn green'
    unselected_bg = 'black'
    #Inverted for selected
    selected_fg = unselected_bg
    selected_bg = unselected_fg
    content_label = 0
    row_height = 16
    width_pixels = 372

    def __init__(self):
        self.num_lines = self.widget.config()['height'][-1]
        self.num_cols  = self.widget.config()['width'][-1]

    def focus_set(self):
        self.frame.focus_set()

    def switch_from(self, event):
        self.app.next_item(self).focus_set()
        return 'break'

    def status_update(self, message):
        for i,label in enumerate(self.label_rows):
            if i == self.num_lines/2:
                content = ('*** %s ***' % message).center(self.width)
            else:
                content = ' '*self.width
            label[self.content_label].set(str(content))

    def place(self):
        self.frame_pos = self.app.current_pos(self.height_pixels)
        self.frame.place(x=self.frame_pos[0], y=self.frame_pos[1], width=self.width_pixels, height=self.height_pixels)

class Frame(Tkinter.Frame):
    def __init__(self, parent, width, height):
        Tkinter.Frame.__init__(self,
                               parent,
                               width=width,
                               height=height*10,
                               borderwidth=4,
                               bg='black',
                               highlightbackground='#004000',
                               highlightcolor='lawn green',
                               highlightthickness=1,
                               relief=Tkinter.SOLID)

class Label(Tkinter.Label):
    def __init__(self, parent, width, text, bg='black', fg='lawn green', anchor='w', padx=2):
        self.sv = Tkinter.StringVar()
        self.sv.set(text)
        Tkinter.Label.__init__(self,
                               parent,
                               width=width,
                               height=1,
                               borderwidth=0,
                               pady=0,
                               padx=padx,
                               font='TkFixedFont',
                               bg=bg,
                               fg=fg,
                               anchor=anchor,
                               textvariable=self.sv,
                               relief=Tkinter.SOLID)

    def set(self, text):
        self.sv.set(text)

    def get(self, text):
        return self.sv.get()

class Scrollable(View):
    buffer = 20 #number of lines above and below to cache
    view_min = None
    view_max = None
    message_class = None
    labels_per_row = 0
    label_widths = None
    double_click_time = 0.5
    def __init__(self, app, height, width, invisible=False):
        self.height = height
        self.width  = width
        self.height_pixels = height*self.row_height
        self.label_widths[self.content_label] = width - sum(self.label_widths)
        self.app    = app
        self.selected = None
        self.selected_addr = None
        self.last_click_time = 0
        self.last_click_index = None
        self.frame = Frame(app.frame,
                           width=self.width,
                           height=self.height)
        if not invisible:
            self.place()
        #self.frame.pack(padx=5,pady=0,side=Tkinter.TOP)
        #self.row_number = self.app.frame.grid_size()[1]
        #self.frame.grid(padx=5)
        self.set_frame_bindings(self.frame)
        self.frame.bind("<s>", self.app.step)
        self.frame.bind("<g>", self.search)
        self.full_height = self.height + 2*self.buffer

        self.frame.bind("<Button-1>", lambda x: self.frame.focus_set())
        self.label_rows = []
        start_row = self.initial_decoration()
        for i in xrange(self.height):
            labels = []
            for j in xrange(self.labels_per_row):
                widget = Label(self.frame, width = self.label_widths[j], text=' ')

                widget.bind("<Button-1>", lambda x,i=i: [self.click(i),self.frame.focus_set()])
                widget.bind("<MouseWheel>", self.mouse_wheel)
                widget.bind("<Button-4>", self.mousewheel_up)
                widget.bind("<Button-5>", self.mousewheel_down)
                widget.grid(row=start_row + i, column=j, padx=0, pady=0, sticky=Tkinter.W)
                labels.append(widget)

            self.label_rows.append(labels)


        self.num_lines = self.height + self.buffer*2
        self.lines = [' ' for i in xrange(self.num_lines)]
        self.num_cols = self.width

        self.view_start = -self.buffer*self.line_size
        self.view_size = self.num_lines * self.line_size
        self.select(0)

    def initial_decoration(self):
        return 0

    def set_frame_bindings(self, frame):
        frame.bind("<Up>", self.keyboard_up)
        frame.bind("<Down>", self.keyboard_down)
        frame.bind("<Next>", self.keyboard_page_down)
        frame.bind("<Prior>", self.keyboard_page_up)
        frame.bind("<MouseWheel>", self.mouse_wheel)
        frame.bind("<Button-4>", self.keyboard_up)
        frame.bind("<Button-5>", self.keyboard_down)
        frame.bind("<Tab>", self.switch_from)
        frame.bind("<space>", self.handle_space)
        frame.bind("<Return>", self.handle_enter)

    def handle_space(self, event):
        return self.activate_item(event)

    def handle_enter(self, event):
        return self.activate_item( event)

    def search(self, event):
        pass

    def update_params(self):
        view_start = self.view_start
        view_size = self.view_size
        if view_start < 0:
            view_size += view_start
            view_start = 0
        return view_start,view_size

    def update(self):
        view_start, view_size = self.update_params()
        if view_size > 0 and self.message_class is not None:
            self.app.send_message(self.message_class(view_start, view_size, view_start, view_size))

    def click(self, index):
        now = time.time()
        if index == self.last_click_index:
            elapsed = now - self.last_click_time
            if elapsed < self.double_click_time:
                self.last_click_index = None
                return self.activate_item(index)
        self.last_click_time = now
        self.last_click_index = index
        print 'bob',index
        self.select(self.index_to_addr(index))

    def index_to_addr(self, index):
        return self.view_start + (self.buffer + index)*self.line_size

    def addr_to_index(self, addr):
        return ((addr - self.view_start)/self.line_size) - self.buffer

    def select(self, addr, index=None):
        if index is None:
            selected = self.addr_to_index(addr)
        else:
            if index < 0 or index >= len(self.label_rows):
                return
            selected = index

        if selected < 0:
            selected = 0

        if selected >= len(self.label_rows):
            selected = len(self.label_rows) - 1

        addr = self.index_to_addr(selected)
        if addr >= self.select_max:
            return
        if selected == self.selected:
            self.selected_addr = addr
            return
        #turn off the old one
        if self.selected is not None:
            widget_selected = self.selected
            if widget_selected >= 0 and widget_selected < len(self.label_rows):
                for widget in self.label_rows[widget_selected]:
                    widget.configure(fg=self.unselected_fg, bg=self.unselected_bg)

        self.selected = selected
        self.selected_addr = addr

        #turn on the new one
        if self.selected is not None:
            widget_selected = self.selected
            if widget_selected >= 0 and widget_selected < len(self.label_rows):
                for widget in self.label_rows[widget_selected]:
                    widget.configure(fg=self.selected_fg, bg=self.selected_bg)

    def mouse_wheel(self, event):
        if event.delta < 0:
            self.mousewheel_up(event)
        else:
            self.mousewheel_down(event)

    def mousewheel_up(self, event):
        self.adjust_view(-1)

    def mousewheel_down(self, event):
        self.adjust_view(1)

    def keyboard_up(self, event):
        self.select(None, self.addr_to_index(self.selected_addr - self.line_size) if self.selected is not None else 0)
        self.centre(self.selected_addr)

    def keyboard_down(self, event):
        self.select(None, self.addr_to_index(self.selected_addr + self.line_size) if self.selected is not None else 0)
        self.centre(self.selected_addr)

    def centre(self, pos):
        if pos is None:
            return
        start = pos - self.full_height*self.line_size/2
        if start < -self.buffer*self.line_size:
            start = -self.buffer*self.line_size
        self.adjust_view((start - self.view_start)/self.line_size)

    def keyboard_page_up(self, event):
        self.adjust_view(-self.height*self.line_size)
        target = self.index_to_addr(self.height/2)
        self.centre(target)
        self.select(target)

    def keyboard_page_down(self, event):
        self.adjust_view(self.height*self.line_size)
        target = self.index_to_addr(self.height/2)
        self.centre(target)
        self.select(target)

    def start_same(self, new_start):
        return new_start == self.view_start

    def set_start(self, new_start):
        self.view_start = new_start

    def adjust_view(self, amount, *args):
        new_start = self.view_start + amount*self.line_size
        if new_start < self.view_min:
            new_start = self.view_min
        if new_start > self.view_max:
            new_start = self.view_max


        if self.start_same(new_start, *args):
            return

        adjust = new_start - self.view_start
        amount = adjust / self.line_size
        self.set_start(new_start, *args)

        if abs(amount) < self.view_size/self.line_size:
            #we can reuse some lines
            if amount < 0:
                start,step,stride = len(self.lines)-1, -1, -1
                unknown_start = self.view_start
                unknown_size = -adjust
            else:
                start,step,stride = 0, len(self.lines), 1
                unknown_start = self.view_start + self.view_size - adjust
                unknown_size = adjust

            for i in xrange(start, step, stride):
                if i + amount >= 0 and i + amount < len(self.lines):
                    new_value = self.lines[i+amount]
                else:
                    new_value = ''
                self.lines[i] = new_value
        else:
            unknown_start = self.view_start
            unknown_size  = self.view_size

        #we now need an update for the region we don't have
        if unknown_start < 0:
            unknown_size += unknown_start
            unknown_start = 0
        if unknown_size > 0:
            #we need more data
            watch_start,watch_size = self.update_params()
            self.request_data(unknown_start, unknown_size, watch_start, watch_size)
        self.redraw()

        #Try to stay where we are
        self.select(self.selected_addr)


    def request_data(self, unknown_start, unknown_size, watch_start, watch_size):
        if self.message_class is not None:
            self.app.send_message(self.message_class(unknown_start, unknown_size, watch_start, watch_size))

class SymbolsSearcher(Scrollable):
    line_size      = 1
    buffer         = 0
    view_min       = 0
    view_max       = 1<<26
    select_max     = view_max
    message_class  = None
    labels_per_row = 2
    content_label  = 1
    label_widths   = [9,0]
    def __init__(self, app, height, width):
        self.parent = None
        self.substrings = {}
        self.contents = []
        super(SymbolsSearcher, self).__init__(app, height, width, invisible=True)

    def set_parent(self, parent):
        self.parent = parent

    def initial_decoration(self):
        self.entry_label = Tkinter.StringVar()
        self.entry_label.trace('w', lambda name, index, mode: self.entry_changed())
        self.text_entry = Tkinter.Entry(self.frame,
                                        width = self.label_widths[self.content_label],
                                        font='TkFixedFont',
                                        bd=0,
                                        highlightthickness=1,
                                        highlightbackground='#004000',
                                        highlightcolor='#008000',
                                        foreground=self.unselected_fg,
                                        background=self.unselected_bg,
                                        insertbackground=self.unselected_fg,
                                        selectbackground=self.selected_bg,
                                        selectforeground=self.selected_fg,
                                        textvariable=self.entry_label,
                                        )
        self.set_frame_bindings(self.text_entry)
        self.goto_label = Label(self.frame, width=5, text='Goto:')
        self.text_entry.grid(row=0,column=1,padx=0, sticky=Tkinter.W)
        self.goto_label.grid(row=0,column=0,padx=0)
        self.separator = Tkinter.Frame(self.frame, height=1, width=1, bg=self.unselected_fg)
        self.separator.grid(pady=4,columnspan=2)
        #return number of rows
        return 2

    def activate_item(self, event):
        if self.selected is not None:
            index = self.index_to_addr(self.selected)
            addr = self.contents[index][0]
            self.hide()
            self.parent.show()
            self.parent.centre(addr)
            self.parent.select(addr)

    def set_frame_bindings(self, frame):
        super(SymbolsSearcher, self).set_frame_bindings(frame)
        #also allow an escape to send us back
        frame.bind("<Escape>",self.stop_searching)

    def entry_changed(self):
        #reset us to the top of the list and redraw
        try:
            self.contents = self.substrings[self.entry_label.get()]
        except KeyError:
            self.contents = []

        first = self.get_first_entry()
        if first is not None:
            self.contents.insert(0, first)

        self.select_max = len(self.contents)
        self.view_start = self.view_min
        self.view_max = max(self.select_max - self.height,0)
        self.select(0)
        self.redraw()

    def stop_searching(self, event):
        self.hide()
        self.parent.show()
        return 'break'

    def search(self, event):
        pass

    def handle_space(self, event):
        return 'break'

    def receive_symbols(self, symbols):
        self.symbols = symbols
        self.substrings = {}
        for addr,name in symbols.iteritems():
            for substring_length in xrange(1,len(name)):
                for start_pos in xrange(0,len(name) + 1 - substring_length):
                    substring = name[start_pos:start_pos + substring_length]
                    try:
                        self.substrings[substring].append( (addr,name) )
                    except KeyError:
                        self.substrings[substring] = [(addr,name)]

        for substring,name_list in self.substrings.iteritems():
            name_list.sort(lambda x,y: cmp(x[0],y[0]))
        self.entry_changed()

    def redraw(self):
        label_index = 0

        for i,row in enumerate(self.label_rows):
            pos = self.view_start + i
            try:
                addr,name = self.contents[pos]
                addr = '%08x' % addr
            except IndexError:
                addr,name = '',''

            row[0].set(addr)
            row[1].set(name)

    def get_first_entry(self):
        contents = self.text_entry.get()
        try:
            addr = int(contents,16)&0xffffffff
        except ValueError:
            return None
        return addr, 'Address %s' % contents

    def show(self):
        self.select(0)
        self.entry_label.set('')
        self.frame.place(x=self.parent.frame_pos[0],
                         y=self.parent.frame_pos[1],
                         height=self.parent.height_pixels,
                         width=self.parent.width_pixels)
        self.app.master.update()
        self.separator.config(width=self.frame.winfo_width() - 30)
        self.frame.focus_set()
        self.text_entry.focus()

    def hide(self):
        self.frame.place_forget()

class Searchable(Scrollable):
    def __init__(self, app, symbols_searcher, height, width):
        self.symbols_searcher = symbols_searcher
        self.symbols = {}
        super(Searchable, self).__init__(app, height, width)
        self.symbols_searcher.set_parent(self)
        self.hidden = False

    def search(self, event):
        self.hide()
        self.symbols_searcher.show()

    def show(self):
        self.frame.place(x=self.frame_pos[0],
                         y=self.frame_pos[1],
                         height=self.height_pixels,
                         width=self.width_pixels)
        self.frame.focus_set()
        self.hidden = False

    def focus_set(self):
        if self.hidden:
            self.symbols_searcher.focus_set()
        else:
            return super(Searchable,self).focus_set()

    def hide(self):
        self.hidden = True
        self.frame.place_forget()

    def receive_symbols(self, symbols):
        self.symbols = symbols
        self.symbols_searcher.receive_symbols(symbols)
        self.redraw()
        #In case those labels have messed us up, reset the selected position
        self.select(self.selected_addr)
        self.centre(self.selected_addr)


class Disassembly(Searchable):
    word_size = 4
    line_size = word_size

    view_min       = -Scrollable.buffer*word_size
    view_max       = 1<<26
    select_max     = view_max
    message_class  = messages.DisassemblyView
    labels_per_row = 3
    content_label  = 2
    label_widths   = [1,1,0]

    def __init__(self, app, symbols_searcher, height, width):
        self.pc = None
        self.last_message = None
        self.addr_lookups = {i:-self.buffer*self.line_size + (self.buffer + i)*self.line_size for i in xrange(height)}
        self.index_lookups = {value:key for key,value in self.addr_lookups.iteritems()}
        self.show_first_label = True
        super(Disassembly,self).__init__(app, symbols_searcher, height, width)


    def set_pc_label(self, pc, label):
        label_index = self.addr_to_index(pc)
        if label_index >= 0 and label_index < len(self.label_rows):
            self.label_rows[label_index][0].set(label)

    def activate_item(self, event=None):
        if self.selected is not None:
            addr = self.index_to_addr(self.selected)
            self.app.toggle_breakpoint(addr)
            self.update_breakpoint(addr, self.selected)

    def update_breakpoint(self, addr, index):
        if addr in self.app.breakpoints:
            self.label_rows[index][1].set('*')
        else:
            self.label_rows[index][1].set(' ')

    def start_same(self, new_start, show_first_label=True):
        return new_start == self.view_start and show_first_label == self.show_first_label

    def set_start(self, new_start, show_first_label=True):
        self.view_start = new_start
        self.show_first_label = show_first_label

    def centre(self, pos):
        #Centering is slightly tricky for us due to the labels. Starting at pos, we go backwards counting
        #how many labels we encounter until we've accounted for the size/2 lines we need
        p = pos
        n = 1 if p in self.symbols else 0
        show_first_label = True
        while n < len(self.label_rows)/2 and p >= 0:
            n += 1
            p -= self.line_size
            if p in self.symbols:
                if n >= len(self.label_rows)/2:
                    #Balls. We can't get this line to appear right in the middle due to the label which needs to go at the start
                    #To get round this, just don't show the label
                    show_first_label = False
                else:
                    n += 1

        start = p - self.buffer*self.line_size
        self.adjust_view((start - self.view_start) / self.line_size, show_first_label)

    def set_pc(self, pc):
        #first turn off the old label
        if pc == self.pc:
            return
        diff = None
        if self.pc is not None:
            self.set_pc_label(self.pc, ' ')
            diff = pc - self.pc


        self.pc = pc
        self.set_pc_label(self.pc, '>')
        if self.app.follow_pc:
            self.centre(self.pc)
        if diff is None or abs(diff) > self.height*self.line_size:
            self.select(self.pc)

    def index_to_addr(self, index):
        return self.addr_lookups[index]

    def addr_to_index(self, addr):
        if addr in self.index_lookups:
            return self.index_lookups[addr]

        #Hmm, we don't have that one, it might be off the end
        max_index = len(self.label_rows) - 1
        max_addr = self.addr_lookups[ max_index ]
        min_addr = self.addr_lookups[ 0 ]
        if addr > max_addr:
            #We can work this out
            return max_index + (addr - max_addr)/self.line_size
        elif addr < min_addr:
            return (addr - min_addr)/self.line_size
        else:
            raise TypeError('Addr to index with misaligned addr %x' % addr)


    def redraw(self):
        line_index = self.buffer
        label_index = 0
        addr = self.view_start + self.buffer*self.line_size
        self.index_lookups = {}

        while label_index < len(self.label_rows):
            if addr in self.symbols and (self.show_first_label or label_index > 0):
                for j in (0,1):
                    self.label_rows[label_index][j].set('=')
                self.label_rows[label_index][2].set('%s:' % self.symbols[addr])
                self.addr_lookups[label_index] = addr
                self.index_lookups[addr] = label_index
                label_index += 1
                if label_index >= len(self.label_rows):
                    break

            indicator_labels = [' ',' ']
            if addr in self.app.breakpoints:
                indicator_labels[1] = '*'
            if addr == self.pc:
                indicator_labels[0] = '>'
            for j,lab in enumerate(indicator_labels):
                self.label_rows[label_index][j].set(lab)

            self.label_rows[label_index][2].set(self.lines[line_index])
            self.addr_lookups[label_index] = addr
            self.index_lookups[addr] = label_index
            line_index += 1
            label_index += 1
            addr += self.line_size

    def receive(self, message):
        line_index = (message.start - self.view_start)/self.word_size

        for (i,dis) in enumerate(message.lines):
            if line_index < 0 or line_index >= len(self.lines):
                continue
            addr = message.start + i*4
            word = struct.unpack('<I',message.memory[i*4:(i+1)*4])[0]
            self.lines[line_index] = '%07x %08x : %s' % (addr,word,dis)
            line_index += 1


class Memory(Searchable):
    line_size = 8
    view_min = -Scrollable.buffer*line_size
    view_max = 1<<26
    select_max = view_max
    labels_per_row = 1
    message_class = messages.MemdumpView
    label_widths = [0]
    printable = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '

    def redraw(self):
        line_index = self.buffer
        label_index = 0
        addr = self.view_start + self.buffer*self.line_size
        while label_index < len(self.label_rows):
            self.label_rows[label_index][self.content_label].set(self.lines[line_index])
            line_index += 1
            label_index += 1
            addr += self.line_size

    def receive(self, message):
        if message.start&7:
            return

        for addr in xrange(message.start, message.start + message.size, 8):
            line_index = (addr - self.view_start)/self.line_size
            if line_index < 0 or line_index >= len(self.lines):
                continue
            data = message.data[addr - message.start:addr + self.line_size - message.start]
            if len(data) < self.line_size:
                data += '??'*(self.line_size-len(data))
            data_string = ' '.join((('%02x' % ord(data[i])) if i < len(data) else '??') for i in xrange(self.line_size))
            ascii_string = ''.join( ('%c' % (data[i] if i < len(data) and data[i] in self.printable else '.') for i in xrange(self.line_size)))
            self.lines[line_index] = '%07x : %s   %s' % (addr, data_string, ascii_string)

    def activate_item(self, item):
        pass

class Tapes(Scrollable):
    line_size = 1
    buffer   = 0
    #view_min = -Scrollable.buffer*line_size
    view_min = 0
    view_max = 64
    select_max = view_max
    labels_per_row = 2
    content_label = 1
    message_class = messages.TapesView
    label_widths=[6,0]
    loaded_message = 'LOADED'
    not_loaded_message = ' '*len(loaded_message)

    def __init__(self, *args, **kwargs):
        self.loaded = None
        self.tape_max = None
        super(Tapes,self).__init__(*args, **kwargs)

    def redraw(self):
        for pos in xrange(self.view_start, self.view_start + len(self.label_rows)):
            index = pos - self.view_start
            self.label_rows[index][self.content_label].set(self.lines[self.buffer + index])
            self.label_rows[index][0].set(self.loaded_message if pos == self.loaded else self.not_loaded_message)

    def receive(self, message):
        self.view_max = max(message.max - self.height,0)
        self.select_max = message.max
        self.tape_max = message.start + message.size
        #TODO: If we just reduced tape_max we'd better turn off LOADED labels for the
        #ones we can't press anymore
        for (i,name) in enumerate(message.tape_list):
            pos = message.start + i
            label_index = pos - self.view_start
            if label_index < 0 or label_index >= len(self.label_rows):
                continue
            self.lines[label_index] = name
            if pos == self.loaded:
                self.label_rows[label_index][0].set(self.loaded_message)
            else:
                self.label_rows[label_index][0].set(self.not_loaded_message)

    def activate_item(self, event=None):
        if self.loaded == self.selected:
            loaded = None
        else:
            loaded = self.selected

        if loaded >= self.tape_max:
            return

        if self.loaded is not None:
            self.label_rows[self.loaded][0].set(self.not_loaded_message)
        self.loaded = loaded
        if loaded is None:
            self.app.send_message(messages.TapeUnload())
        else:
            self.app.send_message(messages.TapeLoad(self.loaded))
        if self.loaded is not None:
            self.label_rows[self.loaded][0].set(self.loaded_message)

class Options(View):
    def __init__(self, app, width, height):
        self.width  = width
        self.height = height
        self.app    = app
        self.label_rows = []
        self.frame = Frame(app.frame,
                           width=self.width,
                           height=self.height)

        #self.frame.pack(padx=5,pady=0,side=Tkinter.TOP,fill='x')
        #self.frame.grid(padx=5,sticky=Tkinter.N+Tkinter.S+Tkinter.E+Tkinter.W)
        self.frame.place()
        self.var = Tkinter.IntVar()
        self.var.set(1 if self.app.follow_pc else 0)
        self.c = Tkinter.Checkbutton(self.frame,
                                     font='TkFixedFont',
                                     highlightbackground='#000000',
                                     highlightcolor='lawn green',
                                     highlightthickness=1,
                                     padx=5,
                                     relief=Tkinter.SOLID,
                                     bg=self.unselected_bg,
                                     fg=self.unselected_fg,
                                     activeforeground=self.unselected_bg,
                                     activebackground=self.unselected_fg,
                                     selectcolor='black',
                                     anchor='w',
                                     text="Follow PC",
                                     variable=self.var,
                                     command=self.cb)
        self.c.pack(side=Tkinter.LEFT)

    def cb(self):
        #The var presently stores 1 or 0, just map that to True or False
        self.app.follow_pc = True if self.var.get() else False
        if self.app.follow_pc:
            self.app.disassembly.centre()

class Registers(View):
    num_entries = 19
    def __init__(self, app, width, height):
        self.height = height
        self.height_pixels = self.height * self.row_height
        self.width  = width
        self.col_width = self.width/3
        self.app    = app
        self.frame = Tkinter.Frame(app.frame,
                                   width=self.width,
                                   height=self.height)

        self.frame.bind("<Tab>", self.switch_from)
        self.place()
        self.label_rows = []
        for i in xrange(self.num_entries):
            widget = Label(self.frame, width=self.col_width, padx=3, text='bobbins')
            widget.grid(row = i%self.height, column=i/self.height, padx=0)
            self.label_rows.append([widget])
        self.num_lines = self.height
        self.num_cols = self.width

    def receive(self, message):
        self.app.set_pc(message.pc)
        for i,reg in enumerate(message.registers):
            self.label_rows[i][0].set( ('%3s : %08x' % (self.register_name(i),reg)).ljust(self.col_width) )

        self.label_rows[16][0].set(('%5s : %8s' % ('MODE',mode_names[message.mode]) ))
        self.label_rows[17][0].set(('%5s : %08x' % ('PC',message.pc)))
        self.label_rows[18][0].set(('%5s : %s' % ('State','Waiting' if message.is_waiting else '')))

    def focus_set(self):
        self.frame.focus_set()
        return 'break'

    def register_name(self, i):
        if i < 12:
            return 'r%d' % i
        else:
            return ['fp','sp','lr','r15','MODE','PC'][i-12]

class Application(Tkinter.Frame):
    unselected_fg = 'lawn green'
    unselected_bg = 'black'
    #Inverted for selected
    selected_fg = unselected_bg
    selected_bg = unselected_fg
    width_pixels = View.width_pixels

    def __init__(self, master, emulator_frame):
        self.emulator = None
        self.master = master
        self.follow_pc = True
        self.emulator_frame = emulator_frame
        self.queue = Queue.Queue()
        self.frame_pos = 0
        self.message_handlers = {messages.Types.DISCONNECT : self.disconnected,
                                 messages.Types.CONNECT    : self.connected,
                                 messages.Types.STATE      : self.receive_register_state,
                                 messages.Types.MEMDATA    : self.receive_memdata,
                                 messages.Types.DISASSEMBLYDATA : self.receive_disassembly,
                                 messages.Types.STOP : self.stop,
                                 messages.Types.TAPE_LIST  : self.receive_tapes,
                                 messages.Types.SYMBOL_DATA : self.receive_symbols,
        }
        Tkinter.Frame.__init__(self, master,width=self.width_pixels + 8,height=720)
        self.stopped = False
        self.pc = None
        self.breakpoints = set()
        self.pack()
        self.createWidgets()
        self.need_symbols = True
        self.client = False
        self.process_messages()
        self.grid_propagate(0)

    def init(self, client):
        self.client = client

    def current_pos(self,height):
        out = 0,self.frame_pos
        self.frame_pos += height
        return out

    def process_messages(self):
        while not self.queue.empty():
            message = self.queue.get_nowait()
            handler = None
            try:
                handler = self.message_handlers[message.type]
            except KeyError:
                print 'Unexpected message %d' % message.type
            if handler:
                handler(message)
        if self.need_symbols and self.client:
            #send a symbols request
            self.send_message( messages.Symbols( [] ) )
        self.after(10, self.process_messages)

    def stop(self, event=None):
        self.stopped = True
        self.stop_button.config(text='resume')
        self.stop_button.config(command=self.resume)
        self.step_button.enable()
        self.send_message(messages.Stop())
        self.memory.centre(0x30000)
        #self.frame.configure(bg=self.disassembly.selected_bg)

    def resume(self):
        self.stopped = False
        self.stop_button.config(text='stop')
        self.stop_button.config(command=self.stop)
        self.step_button.disable()
        self.send_message(messages.Resume())
        #self.frame.configure(bg=self.disassembly.unselected_bg)

    def toggle_breakpoint(self,addr):
        if addr in self.breakpoints:
            self.breakpoints.remove(addr)
            self.send_message(messages.UnsetBreakpoint(addr))
        else:
            self.breakpoints.add(addr)
            self.send_message(messages.SetBreakpoint(addr))

    def toggle_stop(self, event):
        if self.stopped:
            self.resume()
        else:
            self.stop()

    def restart(self):
        #self.send_message(messages.Restart())
        if self.emulator:
            self.emulator.restart()

    def next_item(self, item):
        if item is self.disassembly.symbols_searcher:
            item = self.disassembly
        try:
            index = self.tab_views.index(item)
        except ValueError:
            return None
        try:
            return self.tab_views[index + 1]
        except IndexError:
            #we go back to the emulator
            return self.emulator_frame

    def set_pc(self, pc):
        self.pc = pc
        self.disassembly.set_pc(pc)

    def step(self, event=None):
        if self.stopped:
            self.send_message(messages.Step())

    def createWidgets(self):
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        self.dead = False
        self.frame = Tkinter.Frame(self, width = self.width_pixels, height = 720)
        self.frame.grid()
        self.frame.grid_propagate(0)
        symbols_searcher = SymbolsSearcher(self, width=50, height=12)
        self.disassembly = Disassembly(self, symbols_searcher, width=47, height=14)

        self.registers = Registers(self, width=50, height=8)
        memory_searcher = SymbolsSearcher(self, width=50, height=11)
        self.memory = Memory(self, memory_searcher, width=50, height=13)
        self.tapes = Tapes(self, width=44, height=6)
        self.options = Options(self, width=50, height=3)

        self.button_frame = Tkinter.Frame(self.frame)
        self.button_frame_pos = self.current_pos(100)
        self.stop_button = Button(self.button_frame, 'stop', self.stop)
        #self.stop_button.pack(side=Tkinter.LEFT, pady=6, padx=5)
        self.stop_button.grid(row=0,column=0,pady=6,padx=5)

        self.step_button = Button(self.button_frame, 'step', self.step, state=Tkinter.DISABLED)
        #self.step_button.pack(side=Tkinter.LEFT, pady=6, padx=5)
        self.step_button.grid(row=0,column=1,pady=6,padx=5)

        self.restart_button = Button(self.button_frame, 'restart', self.restart)
        #self.restart_button.pack(side=Tkinter.LEFT, pady=6, padx=2)
        self.restart_button.grid(row=0,column=2,pady=6,padx=5)
        self.button_frame.place(x=self.button_frame_pos[0],
                                y=self.button_frame_pos[1],
                                width=self.registers.width_pixels,
                                height=100)

        self.views = [self.disassembly, self.registers, self.memory, self.tapes, self.options]
        self.tab_views = [self.disassembly, self.memory, self.tapes, self.options]

        self.queue.put(messages.Disconnect())

    def send_message(self, message):
        self.client.send(message)

    def message_handler(self, message):
        if not self.dead:
            self.queue.put(message)

    def status_update(self, message):
        """Update the views to show that we're disconnected"""
        for view in self.views:
            view.status_update(message)

    def disconnected(self, message):
        try:
            self.status_update('DISCONNECTED')
        except (Tkinter.TclError,RuntimeError) as e:
            self.dead = True
            #This can happen if we're bringing everything down
            print 'Ignoring TCL error during disconnect',self.dead

    def connected(self, message=None):
        self.status_update('CONNECTED')
        self.memory.update()
        self.disassembly.update()
        self.tapes.update()


    def receive_register_state(self, message):
        self.registers.receive(message)

    def receive_disassembly(self, message):
        self.disassembly.receive(message)
        self.disassembly.redraw()

    def receive_memdata(self, message):
        self.memory.receive(message)
        self.memory.redraw()

    def receive_tapes(self, message):
        self.tapes.receive(message)
        self.tapes.redraw()

    def receive_symbols(self, symbols):
        self.need_symbols = False
        self.disassembly.receive_symbols(symbols)
        self.memory.receive_symbols(symbols)


def run():
    #import hanging_threads
    root = Tkinter.Tk()
    root.tk_setPalette(background='black',
                       highlightbackground='lawn green')
    app = Application(master=root)
    with messages.Client('localhost', 0x4141, callback=app.message_handler) as client:
        print client
        app.init(client)
        app.mainloop()
    root.destroy()

def switch_to_disassembly(app, event):
    app.disassembly.focus_set()
    return 'break'

def main():
    import pygame
    import emulate
    import os
    root = Tkinter.Tk()
    root.tk_setPalette(background='black',
                       highlightbackground='lawn green')
    embed = Tkinter.Frame(root, width = 960, height = 720)
    os.environ['SDL_WINDOWID'] = str(embed.winfo_id())
    debugger = Tkinter.Frame(root)
    embed.pack(side=Tkinter.LEFT)
    app = Application(master=debugger, emulator_frame=embed)
    debugger.pack(side=Tkinter.TOP)

    try:
        with messages.Client('localhost', 0x4141, callback=app.message_handler) as client:
            print client
            app.client = client
            #app.mainloop()
            app.update()
            #os.environ['SDL_VIDEODRIVER'] = 'windib'
            embed.focus_set()
            emulate.init()
            emulator = emulate.Emulator()
            app.emulator = emulator
            embed.bind("<Key>", emulator.key_up)
            root.bind("<Escape>", app.toggle_stop)
            embed.bind("<KeyRelease>", emulator.key_down)
            embed.bind("<Button-1>", lambda x: embed.focus_set())
            #filthy hack to get tab order working
            embed.bind("<Tab>", lambda event: switch_to_disassembly(app, event))

            emulator.run( callback=app.update )
    finally:
        try:
            root.destroy()
        except Tkinter.TclError as e:
            pass

if __name__ == '__main__':
    main()
