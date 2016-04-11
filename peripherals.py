import Tkinter
import random
import disassemble
import messages
import string
import struct
import itertools
import sys
import Queue

def insert_wrapper(func):
    def wrapper(self, *args, **kwargs):
        self.configure(state=Tkinter.NORMAL)
        func(self,*args,**kwargs)
        self.configure(state=Tkinter.DISABLED)
    return wrapper

Tkinter.Text.insert = insert_wrapper(Tkinter.Text.insert)
Tkinter.Text.delete = insert_wrapper(Tkinter.Text.delete)

mode_names = ['USR','FIQ','IRQ','SUP']

class View(object):
    unselected_fg = 'lawn green'
    unselected_bg = 'black'
    #Inverted for selected
    selected_fg = unselected_bg
    selected_bg = unselected_fg
    content_label = 0

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


class Scrollable(View):
    buffer = 20 #number of lines above and below to cache
    view_min = None
    view_max = None
    message_class = None
    labels_per_row = 0
    label_widths = None
    def __init__(self, app, height, width):
        self.height = height
        self.width  = width
        self.label_widths[self.content_label] = width
        self.app    = app
        self.widget_rows = []
        self.selected = None
        self.selected_addr = None
        self.frame = Tkinter.Frame(app.frame,
                                   width=self.width,
                                   height=self.height,
                                   borderwidth=4,
                                   bg='black',
                                   highlightbackground='lawn green',
                                   highlightcolor='white',
                                   highlightthickness=1,
                                   relief=Tkinter.SOLID)
        self.frame.pack(padx=5,pady=0,side=Tkinter.TOP)
        self.frame.bind("<Up>", self.keyboard_up)
        self.frame.bind("<Down>", self.keyboard_down)
        self.frame.bind("<Next>", self.keyboard_page_down)
        self.frame.bind("<Prior>", self.keyboard_page_up)
        self.frame.bind("<MouseWheel>", self.mouse_wheel)
        self.frame.bind("<Button-4>", self.keyboard_up)
        self.frame.bind("<Button-5>", self.keyboard_down)
        self.frame.bind("<Tab>", self.switch_from)

        self.frame.bind("<Button-1>", lambda x: self.frame.focus_set())
        self.label_rows = []
        for i in xrange(self.height + self.buffer*2):
            widgets = []
            labels = []
            for j in xrange(self.labels_per_row):
                sv = Tkinter.StringVar()
                sv.set(' ')
                if 0 <= i-self.buffer < self.height:
                    widget = Tkinter.Label(self.frame,
                                           width = self.label_widths[j],
                                           height = 1,
                                           borderwidth = 0,
                                           pady=0,
                                           padx=2,
                                           font='TkFixedFont',
                                           bg=self.unselected_bg,
                                           fg=self.unselected_fg,
                                           anchor='w',
                                           textvariable=sv,
                                           relief=Tkinter.SOLID)
                    widget.bind("<Button-1>", lambda x,i=i: [self.select(self.view_start + i*self.line_size),self.frame.focus_set()])
                    widget.bind("<MouseWheel>", self.mouse_wheel)
                    widget.bind("<Button-4>", self.keyboard_up)
                    widget.bind("<Button-5>", self.keyboard_down)
                    widget.grid(row=i-self.buffer, column=j, padx=0, pady=0)
                    widgets.append(widget)
                labels.append(sv)

            if 0 <= i-self.buffer < self.height:
                self.widget_rows.append(widgets)
            self.label_rows.append(labels)


        self.num_lines = self.height + self.buffer*2
        self.num_cols = self.width

        self.view_start = -self.buffer*self.line_size
        self.view_size = self.num_lines * self.line_size
        self.select(0)

    def update_params(self):
        view_start = self.view_start
        view_size = self.view_size
        if view_start < 0:
            view_size += view_start
            view_start = 0
        return view_start,view_size

    def update(self):
        view_start, view_size = self.update_params()
        if view_size > 0:
            self.app.send_message(self.message_class(view_start, view_size, view_start, view_size))

    def select(self, addr):
        selected = (addr - self.view_start)/self.line_size
        if selected < 0 or selected >= len(self.label_rows):
            selected = None
        #turn off the old one
        if self.selected is not None:
            widget_selected = self.selected - self.buffer
            if widget_selected >= 0 and widget_selected < len(self.widget_rows):
                for widget in self.widget_rows[widget_selected]:
                    widget.configure(fg=self.unselected_fg, bg=self.unselected_bg)

        self.selected = selected
        self.selected_addr = addr
        #turn on the new one
        if self.selected is not None:
            widget_selected = self.selected - self.buffer
            if widget_selected >= 0 and widget_selected < len(self.widget_rows):
                for widget in self.widget_rows[widget_selected]:
                    widget.configure(fg=self.selected_fg, bg=self.selected_bg)

    def mouse_wheel(self, event):
        if event.delta < 0:
            self.keyboard_up(event)
        else:
            self.keyboard_down(event)

    def keyboard_up(self, event):
        self.adjust_view(-1)

    def keyboard_down(self, event):
        self.adjust_view(1)

    def keyboard_page_up(self, event):
        self.adjust_view(-self.height)

    def keyboard_page_down(self, event):
        self.adjust_view(self.height)

    def adjust_view(self, amount):
        if amount == 0:
            return
        new_start = self.view_start + amount*self.line_size
        if new_start < self.view_min:
            new_start = self.view_min
        if new_start > self.view_max:
            new_start = self.view_max

        if new_start == self.view_start:
            return

        adjust = new_start - self.view_start
        amount = adjust / self.line_size
        self.view_start = new_start

        self.select(self.selected_addr)

        if abs(amount) < self.view_size/self.line_size:
            #we can reuse some labels
            if amount < 0:
                start,step,stride = len(self.label_rows)-1, -1, -1
                unknown_start = self.view_start
                unknown_size = -adjust
            else:
                start,step,stride = 0, len(self.label_rows), 1
                unknown_start = self.view_start + self.view_size -adjust
                unknown_size = adjust

            for i in xrange(start, step, stride):
                if i + amount >= 0 and i + amount < len(self.label_rows):
                    new_value = (self.label_rows[i+amount][j].get() for j in xrange(self.labels_per_row))
                else:
                    new_value = (' ' for j in xrange(self.labels_per_row))
                for j,val in enumerate(new_value):
                    self.label_rows[i][j].set(val)

        #we now need an update for the region we don't have
        if unknown_start < 0:
            unknown_size += unknown_start
            unknown_start = 0
        if unknown_size <= 0:
            #no point
            return
        watch_start,watch_size = self.update_params()
        self.app.send_message(self.message_class(unknown_start, unknown_size, watch_start, watch_size))

        #self.update()


class Disassembly(Scrollable):
    word_size = 4
    line_size = word_size

    view_min = -Scrollable.buffer*word_size
    view_max = 1<<26
    message_class = messages.DisassemblyView
    labels_per_row = 3
    content_label = 2
    label_widths = [1,1,0]

    def __init__(self, *args, **kwargs):
        self.pc = None
        super(Disassembly,self).__init__(*args, **kwargs)

    def set_pc_label(self, pc, label):
        label_index = (pc - self.view_start)/self.word_size
        if label_index >= 0 and label_index < len(self.label_rows):
            self.label_rows[label_index][0].set(label)

    def set_pc(self, pc):
        #first turn off the old label
        if self.pc is not None:
            self.set_pc_label(self.pc, ' ')

        self.pc = pc
        self.set_pc_label(self.pc, '>')

    def receive(self, message):
        for (i,dis) in enumerate(message.lines):
            addr = message.start + i*4
            label_index = (addr - self.view_start)/self.word_size
            if label_index < 0 or label_index >= len(self.label_rows):
                continue
            word = struct.unpack('<I',message.memory[i*4:(i+1)*4])[0]
            line = '%07x %08x : %s' % (addr,word,dis)
            self.label_rows[label_index][2].set(line)

class Memory(Scrollable):
    line_size = 8
    view_min = -Scrollable.buffer*line_size
    view_max = 1<<26
    labels_per_row = 1
    message_class = messages.MemdumpView
    label_widths = [0]
    printable = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '

    def receive(self, message):
        if message.start&7:
            return

        for addr in xrange(message.start, message.start + message.size, 8):
            label_index = (addr - self.view_start)/self.line_size
            if label_index < 0 or label_index >= len(self.label_rows):
                continue
            data = message.data[addr - message.start:addr + self.line_size - message.start]
            if len(data) < self.line_size:
                data += '??'*(self.line_size-len(data))
            data_string = ' '.join((('%02x' % ord(data[i])) if i < len(data) else '??') for i in xrange(self.line_size))
            ascii_string = ''.join( ('%c' % (data[i] if i < len(data) and data[i] in self.printable else '.') for i in xrange(self.line_size)))
            self.label_rows[label_index][0].set('%07x : %s   %s' % (addr,data_string,ascii_string))

class Registers(View):
    num_entries = 18
    def __init__(self, app, width, height):
        self.height = height
        self.width  = width
        self.col_width = self.width/3
        self.app    = app
        self.widgets = []
        self.frame = Tkinter.Frame(app.frame,
                                   width=self.width,
                                   height=self.height,
                                   borderwidth=4,
                                   bg='black',
                                   highlightbackground='lawn green',
                                   highlightcolor='white',
                                   highlightthickness=1,
                                   relief=Tkinter.SOLID)
        self.frame.bind("<Tab>", self.switch_from)
        self.frame.pack(padx=0,pady=0,side=Tkinter.TOP)
        self.label_rows = []
        for i in xrange(self.num_entries):
            sv = Tkinter.StringVar()
            sv.set('bobbins')
            widget = Tkinter.Label(self.frame,
                                   width = self.col_width,
                                   height = 1,
                                   borderwidth = 0,
                                   pady=0,
                                   padx=3,
                                   font='TkFixedFont',
                                   bg=self.unselected_bg,
                                   fg=self.unselected_fg,
                                   anchor='w',
                                   textvariable=sv,
                                   relief=Tkinter.SOLID)
            widget.grid(row = i%self.height, column=i/self.height, padx=0)
            self.widgets.append(widget)
            self.label_rows.append([sv])
        self.num_lines = self.height
        self.num_cols = self.width

    def receive(self, message):
        self.app.set_pc(message.pc)
        for i,reg in enumerate(message.registers):
            self.label_rows[i][0].set( ('%3s : %08x' % (self.register_name(i),reg)).ljust(self.col_width) )

        self.label_rows[16][0].set(('%5s : %8s' % ('MODE',mode_names[message.mode]) ))
        self.label_rows[17][0].set(('%5s : %08x' % ('PC',message.pc)))

    def focus_set(self):
        self.frame.focus_set()
        return 'break'

    def register_name(self, i):
        if i < 12:
            return 'r%d' % i
        else:
            return ['fp','sp','lr','r15','MODE','PC'][i-12]

class Button(Tkinter.Button):
    unselected_fg = 'lawn green'
    unselected_bg = 'black'
    #Inverted for selected
    selected_fg = unselected_bg
    selected_bg = unselected_fg

    def __init__(self, parent, text, callback):
        self.parent = parent
        self.callback = callback
        Tkinter.Button.__init__(self,
                                self.parent,
                                width=6,
                                pady=2,
                                highlightbackground=self.unselected_fg,
                                highlightcolor=self.unselected_fg,
                                highlightthickness=1,
                                fg=self.unselected_fg,
                                bg=self.unselected_bg,
                                activebackground=self.selected_bg,
                                activeforeground=self.selected_fg,
                                command=self.callback,
                                text=text,
                                relief=Tkinter.SOLID
                                )

class Application(Tkinter.Frame):
    unselected_fg = 'lawn green'
    unselected_bg = 'black'
    #Inverted for selected
    selected_fg = unselected_bg
    selected_bg = unselected_fg

    def __init__(self, master, emulator_frame):
        self.emulator = None
        self.emulator_frame = emulator_frame
        self.queue = Queue.Queue()
        self.message_handlers = {messages.Types.DISCONNECT : self.disconnected,
                                 messages.Types.CONNECT    : self.connected,
                                 messages.Types.STATE      : self.receive_register_state,
                                 messages.Types.MEMDATA    : self.receive_memdata,
                                 messages.Types.DISASSEMBLYDATA : self.receive_disassembly,
        }
        Tkinter.Frame.__init__(self, master)
        self.stopped = False
        self.pc = None
        self.breakpoints = {}
        self.pack()
        self.createWidgets()
        self.process_messages()

    def process_messages(self):
        try:
            while True:
                message = self.queue.get_nowait()
                try:
                    handler = self.message_handlers[message.type]
                    handler(message)
                except KeyError:
                    print 'Unexpected message %d' % message.type
        except Queue.Empty:
            pass
        self.after(100, self.process_messages)

    def stop(self):
        self.stopped = True
        self.stop_button['text'] = 'resume'
        self.stop_button['command'] = self.resume
        self.send_message(messages.Stop())
        #self.frame.configure(bg=self.disassembly.selected_bg)

    def resume(self):
        self.stopped = False
        self.stop_button['text'] = 'stop'
        self.stop_button['command'] = self.stop
        self.send_message(messages.Resume())
        #self.frame.configure(bg=self.disassembly.unselected_bg)

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
        try:
            index = self.views.index(item)
        except ValueError:
            return None
        try:
            return self.views[index + 1]
        except IndexError:
            #we go back to the emulator
            return self.emulator_frame

    def set_pc(self, pc):
        self.pc = pc
        self.disassembly.set_pc(pc)

    def createWidgets(self):
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        self.dead = False
        self.frame = Tkinter.Frame(self, width = 240, height = 720)
        self.frame.pack(side=Tkinter.TOP)
        self.disassembly = Disassembly(self, width=47, height=14)
        self.registers = Registers(self, width=50, height=8)
        self.memory = Memory(self, width=50, height=13)

        self.stop_button = Button(self.frame, 'stop', self.stop)
        self.stop_button.pack(side=Tkinter.LEFT, pady=6, padx=5)

        self.restart_button = Button(self.frame, 'restart', self.restart)
        self.restart_button.pack(side=Tkinter.LEFT, pady=6, padx=2)

        self.views = [self.disassembly, self.registers, self.memory]

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


    def receive_register_state(self, message):
        self.registers.receive(message)

    def receive_disassembly(self, message):
        self.disassembly.receive(message)

    def receive_memdata(self, message):
        self.memory.receive(message)

def run():
    #import hanging_threads
    root = Tkinter.Tk()
    root.tk_setPalette(background='black',
                       highlightbackground='lawn green')
    app = Application(master=root)
    with messages.Client('localhost', 0x4141, callback=app.message_handler) as client:
        print client
        app.client = client
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
