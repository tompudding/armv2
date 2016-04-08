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

def register_name(i):
    if i < 12:
        return 'r%d' % i
    else:
        return ['fp','sp','lr','r15'][i-12]

class View(object):
    def __init__(self):
        self.num_lines = self.widget.config()['height'][-1]
        self.num_cols  = self.widget.config()['width'][-1]

class Disassembly(View):
    def __init__(self, app, height, width):
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        self.height = height
        self.width  = width
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
        self.frame.pack(padx=5,pady=5)
        self.labels = []
        for i in xrange(self.height):
            sv = Tkinter.StringVar()
            sv.set('bobbins')
            widget = Tkinter.Label(self.frame,
                                   width = self.width,
                                   height = 1,
                                   font='TkFixedFont',
                                   bg='black',
                                   fg='lawn green',
                                   anchor='w',
                                   textvariable=sv,
                                   relief=Tkinter.SOLID)
            widget.pack(padx=5,pady=0)
            self.widgets.append(widget)
            self.labels.append(sv)

        #super(Disassembly, self).__init__()
        self.num_lines = self.height
        self.num_cols = self.width
        #for i in xrange(self.num_lines):
        #    self.widget.insert(Tkinter.INSERT, '%50s' % ''.join(random.choice(alphabet) for j in xrange(50)))

        self.view_start = 0
        self.view_size = self.num_lines * 4

    def status_update(self, message):
        for i,label in enumerate(self.labels):
            if i == self.num_lines/2:
                content = ('*** %s ***' % message).center(self.width)
            else:
                content = ' '*self.width
            label.set(str(content))

    def receive(self, message):
        for i,(dis,label) in enumerate(itertools.izip(message.lines,self.labels)):
            addr = message.start + i*4
            word = struct.unpack('<I',message.memory[i*4:(i+1)*4])[0]
            arrow = '>' if addr == self.app.pc else ''
            bpt   = '*' if addr in self.app.breakpoints else ' '
            line = '%1s%s%07x %08x : %s' % (arrow,bpt,addr,word,dis)
            label.set(line)

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

    def resume(self):
        self.stopped = False
        self.stop_button['text'] = 'stop'
        self.stop_button['command'] = self.stop

    def createWidgets(self):
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        self.dead = False
        self.disassembly = Disassembly(self, width=50, height=14)
        self.registers = Tkinter.Text(self,
                                      width=50,
                                      height=8,
                                      font='TkFixedFont',
                                      borderwidth=4,
                                      bg='black',
                                      fg='lawn green',
                                      highlightbackground='lawn green',
                                      highlightcolor='lawn green',
                                      highlightthickness=1,
                                      state=Tkinter.DISABLED,
                                      relief=Tkinter.SOLID)
        self.registers.pack(padx=5,pady=5)
        for i in xrange(8):
            self.registers.insert(Tkinter.INSERT, '%50s' % ''.join(random.choice(alphabet) for j in xrange(50)))

        self.memory = Tkinter.Text(self,
                                   width=50,
                                   height=13,
                                   font='TkFixedFont',
                                   borderwidth=4,
                                   bg='black',
                                   fg='lawn green',
                                   highlightbackground='lawn green',
                                   highlightcolor='lawn green',
                                   highlightthickness=1,
                                   state=Tkinter.DISABLED,
                                   relief=Tkinter.SOLID)
        self.memory.pack(padx=5,pady=5)
        for i in xrange(13):
            self.memory.insert(Tkinter.INSERT, '%50s' % ''.join(random.choice(alphabet) for j in xrange(50)))

        self.stop_button = Tkinter.Button(self, width=10)
        self.stop_button["text"] = "stop"
        self.stop_button["fg"]   = "red"
        self.stop_button["command"] =  self.stop

        self.stop_button.pack({"side": "left"})
        self.views = [self.disassembly, self.memory, self.registers]
        for view in self.views[1:]:
            view.num_lines = view.config()['height'][-1]
            view.width = view.config()['width'][-1]

        self.memory.view_start = 0
        self.memory.view_size  = self.memory.num_lines * 8

        self.queue.put(messages.Disconnect())

    def message_handler(self, message):
        if not self.dead:
            self.queue.put(message)

    def status_update(self, message):
        """Update the views to show that we're disconnected"""
        for view in self.views[:1]:
            view.status_update(message)

        for view in self.views[1:]:
            view.delete('1.0',Tkinter.END)
            for i in xrange(view.num_lines):
                if i == view.num_lines/2:
                    content = ('*** %s ***' % message).center(view.width)
                else:
                    content = ' '*view.width
                view.insert('%d.0' % (i+1), content + '\n')

    def disconnected(self, message):
        try:
            self.status_update('DISCONNECTED')
        except (Tkinter.TclError,RuntimeError) as e:
            self.dead = True
            #This can happen if we're bringing everything down
            print 'Ignoring TCL error during disconnect',self.dead

    def connected(self, message=None):
        self.status_update('CONNECTED')
        self.client.send(messages.MemdumpView(self.memory.view_start, self.memory.view_size))
        self.client.send(messages.DisassemblyView(self.disassembly.view_start, self.disassembly.view_size))

    def receive_register_state(self, message):
        #We'll do 3 columns
        view = self.registers
        lines = [list() for i in xrange(view.num_lines)]
        col_width = view.width/3
        self.pc = message.pc
        for i,reg in enumerate(message.registers):
            lines[i%len(lines)].append( ('%3s : %08x' % (register_name(i),reg)).ljust(col_width) )

        pos = len(message.registers)
        lines[pos%len(lines)].append( ('%5s : %8s' % ('MODE',mode_names[message.mode]) ))
        lines[(pos+1)%len(lines)].append( ('%5s : %08x' % ('PC',message.pc) ))
        self.registers.delete('1.0',Tkinter.END)
        for i,line in enumerate(lines):
            line = ''.join(line).ljust(view.width)
            view.insert('%d.0' % (i+1), line + '\n')

    def receive_disassembly(self, message):
        self.disassembly.receive(message)

    def receive_memdata(self, message):
        view = self.memory
        display_width = 8
        view.delete('1.0',Tkinter.END)
        for i in xrange(view.num_lines):
            addr = view.view_start + i*display_width
            data = message.data[i*display_width:(i+1)*display_width]
            if len(data) < display_width:
                data += '??'*(display_width-len(data))
            data_string = ' '.join((('%02x' % ord(data[i])) if i < len(data) else '??') for i in xrange(display_width))
            ascii_string = ''.join( ('%c' % (data[i] if i < len(data) and data[i] in string.printable else '.') for i in xrange(display_width)))
            line = '%07x : %s   %s' % (addr,data_string,ascii_string)
            if 0:# or addr == self.selected:
                view.insert('%d.0' % (i+1), line + '\n')
            else:
                view.insert('%d.0' % (i+1), line + '\n')

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
    debugger.pack(side=Tkinter.RIGHT)

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
