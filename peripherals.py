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

    def __init__(self):
        self.num_lines = self.widget.config()['height'][-1]
        self.num_cols  = self.widget.config()['width'][-1]


    def status_update(self, message):
        for i,label in enumerate(self.labels):
            if i == self.num_lines/2:
                content = ('*** %s ***' % message).center(self.width)
            else:
                content = ' '*self.width
            label.set(str(content))


class Scrollable(View):
    buffer = 20 #number of lines above and below to cache
    view_min = None
    view_max = None
    message_class = None
    def __init__(self, app, height, width):
        self.height = height
        self.width  = width
        self.app    = app
        self.widgets = []
        self.selected = None
        self.selected_addr = None
        self.frame = Tkinter.Frame(app,
                                   width=self.width,
                                   height=self.height,
                                   borderwidth=4,
                                   bg='black',
                                   highlightbackground='lawn green',
                                   highlightcolor='lawn green',
                                   highlightthickness=1,
                                   relief=Tkinter.SOLID)
        self.frame.pack(padx=5,pady=5,side=Tkinter.TOP)
        self.frame.bind("<Up>", self.keyboard_up)
        self.frame.bind("<Down>", self.keyboard_down)
        self.frame.bind("<Next>", self.keyboard_page_down)
        self.frame.bind("<Prior>", self.keyboard_page_up)
        self.frame.bind("<MouseWheel>", self.mouse_wheel)
        self.frame.bind("<Button-4>", self.keyboard_up)
        self.frame.bind("<Button-5>", self.keyboard_down)

        self.frame.bind("<Button-1>", lambda x: self.frame.focus_set())
        self.labels = []
        for i in xrange(self.height + self.buffer*2):
            sv = Tkinter.StringVar()
            sv.set('bobbins')
            if 0 <= i-self.buffer < self.height:
                widget = Tkinter.Label(self.frame,
                                       width = self.width,
                                       height = 1,
                                       borderwidth = 0,
                                       pady=0,
                                       padx=0,
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
                widget.pack(padx=5,pady=0)
                self.widgets.append(widget)
            self.labels.append(sv)

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
        if selected < 0 or selected >= len(self.labels):
            selected = None
        #turn off the old one
        if self.selected is not None:
            widget_selected = self.selected - self.buffer
            if widget_selected >= 0 and widget_selected < len(self.widgets):
                self.widgets[widget_selected].configure(fg=self.unselected_fg, bg=self.unselected_bg)

        self.selected = selected
        self.selected_addr = addr
        #turn on the new one
        if self.selected is not None:
            widget_selected = self.selected - self.buffer
            if widget_selected >= 0 and widget_selected < len(self.widgets):
                self.widgets[widget_selected].configure(fg=self.selected_fg, bg=self.selected_bg)

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
                start,step,stride = len(self.labels)-1, -1, -1
                unknown_start = self.view_start
                unknown_size = -adjust
            else:
                start,step,stride = 0, len(self.labels), 1
                unknown_start = self.view_start + self.view_size -adjust
                unknown_size = adjust

            for i in xrange(start, step, stride):
                if i + amount >= 0 and i + amount < len(self.labels):
                    new_value = self.labels[i+amount].get()
                else:
                    new_value = ' '*self.width
                self.labels[i].set(new_value)

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

    def receive(self, message):
        for (i,dis) in enumerate(message.lines):
            addr = message.start + i*4
            label_index = (addr - self.view_start)/self.word_size
            if label_index < 0 or label_index >= len(self.labels):
                continue
            word = struct.unpack('<I',message.memory[i*4:(i+1)*4])[0]
            arrow = '>' if addr == self.app.pc else ''
            bpt   = '*' if addr in self.app.breakpoints else ' '
            line = '%1s%s%07x %08x : %s' % (arrow,bpt,addr,word,dis)
            self.labels[label_index].set(line)

class Memory(Scrollable):
    line_size = 8
    view_min = -Scrollable.buffer*line_size
    view_max = 1<<26
    message_class = messages.MemdumpView
    printable = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '

    def receive(self, message):
        if message.start&7:
            return

        for addr in xrange(message.start, message.start + message.size, 8):
            label_index = (addr - self.view_start)/self.line_size
            if label_index < 0 or label_index >= len(self.labels):
                continue
            data = message.data[addr - message.start:addr + self.line_size - message.start]
            if len(data) < self.line_size:
                data += '??'*(self.line_size-len(data))
            data_string = ' '.join((('%02x' % ord(data[i])) if i < len(data) else '??') for i in xrange(self.line_size))
            ascii_string = ''.join( ('%c' % (data[i] if i < len(data) and data[i] in self.printable else '.') for i in xrange(self.line_size)))
            self.labels[label_index].set('%07x : %s   %s' % (addr,data_string,ascii_string))


class Registers(View):
    num_entries = 18
    def __init__(self, app, width, height):
        self.height = height
        self.width  = width
        self.col_width = self.width/3
        self.app    = app
        self.widgets = []
        self.frame = Tkinter.Frame(app,
                                   width=self.width,
                                   height=self.height,
                                   borderwidth=4,
                                   bg='black',
                                   highlightbackground='lawn green',
                                   highlightcolor='lawn green',
                                   highlightthickness=1,
                                   relief=Tkinter.SOLID)
        self.frame.pack(padx=5,pady=5,side=Tkinter.TOP)
        self.labels = []
        for i in xrange(self.num_entries):
            sv = Tkinter.StringVar()
            sv.set('bobbins')
            widget = Tkinter.Label(self.frame,
                                   width = self.col_width,
                                   height = 1,
                                   borderwidth = 0,
                                   pady=0,
                                   padx=4,
                                   font='TkFixedFont',
                                   bg=self.unselected_bg,
                                   fg=self.unselected_fg,
                                   anchor='w',
                                   textvariable=sv,
                                   relief=Tkinter.SOLID)
            widget.grid(row = i%self.height, column=i/self.height)
            self.widgets.append(widget)
            self.labels.append(sv)
        self.num_lines = self.height
        self.num_cols = self.width

    def receive(self, message):
        self.app.pc = message.pc
        for i,reg in enumerate(message.registers):
            self.labels[i].set( ('%3s : %08x' % (self.register_name(i),reg)).ljust(self.col_width) )

        self.labels[16].set(('%5s : %8s' % ('MODE',mode_names[message.mode]) ))
        self.labels[17].set(('%5s : %08x' % ('PC',message.pc)))

    def register_name(self, i):
        if i < 12:
            return 'r%d' % i
        else:
            return ['fp','sp','lr','r15','MODE','PC'][i-12]



class Application(Tkinter.Frame):
    def __init__(self, master):
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

    def resume(self):
        self.stopped = False
        self.stop_button['text'] = 'stop'
        self.stop_button['command'] = self.stop
        self.send_message(messages.Resume())

    def createWidgets(self):
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        self.dead = False
        self.disassembly = Disassembly(self, width=50, height=14)
        self.registers = Registers(self, width=50, height=8)
        self.memory = Memory(self, width=50, height=13)

        self.stop_button = Tkinter.Button(self, width=10)
        self.stop_button["text"] = "stop"
        self.stop_button["fg"]   = "red"
        self.stop_button["command"] =  self.stop

        self.stop_button.pack({"side": "left"})
        self.views = [self.disassembly, self.memory, self.registers]

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
    app = Application(master=debugger)
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
            embed.bind("<Key>", emulator.key_up)
            embed.bind("<KeyRelease>", emulator.key_down)
            embed.bind("<Button-1>", lambda x: embed.focus_set())
            emulator.run( callback=app.update )
    finally:
        try:
            root.destroy()
        except Tkinter.TclError as e:
            pass

if __name__ == '__main__':
    main()
