import Tkinter
import random
import disassemble
import messages

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

class Application(Tkinter.Frame):
    def __init__(self, master):
        self.message_handlers = {messages.Types.DISCONNECT : self.disconnected,
                                 messages.Types.CONNECT    : self.connected,
                                 messages.Types.STATE      : self.receive_register_state}
        Tkinter.Frame.__init__(self, master)
        self.stopped = False
        self.pack()
        self.createWidgets()

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
        self.disassembly = Tkinter.Text(self,
                                        width=50,
                                        height=14,
                                        font='TkFixedFont',
                                        borderwidth=4,
                                        bg='black',
                                        fg='lawn green',
                                        highlightbackground='lawn green',
                                        highlightcolor='lawn green',
                                        highlightthickness=1,
                                        state=Tkinter.DISABLED,
                                        relief=Tkinter.SOLID)
        self.disassembly.num_lines = self.disassembly.config()['height'][-1]
        self.disassembly.width = self.disassembly.config()['width'][-1]
        self.disassembly.pack(padx=5,pady=5)
        for i in xrange(14):
            self.disassembly.insert(Tkinter.INSERT, '%50s' % ''.join(random.choice(alphabet) for j in xrange(50)))

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
        for view in self.views:
            view.num_lines = view.config()['height'][-1]
            view.width = view.config()['width'][-1]

        self.memory.view_start = 0
        self.memory.view_size  = self.memory.num_lines * 8

        self.disassembly.view_start = 0
        self.disassembly.view_size  = self.disassembly.num_lines * 4

        self.disconnected()

    def message_handler(self, message):
        try:
            handler = self.message_handlers[message.type]
        except KeyError:
            print 'Unexpected message %d' % message.type
            return
        handler(message)

    def status_update(self, message):
        """Update the views to show that we're disconnected"""
        for view in self.views:
            view.delete('1.0',Tkinter.END)
            for i in xrange(view.num_lines):
                if i == view.num_lines/2:
                    content = ('*** %s ***' % message).center(view.width)
                else:
                    content = ' '*view.width
                view.insert('%d.0' % (i+1), content + '\n')

    def disconnected(self, message=None):
        self.status_update('DISCONNECTED')

    def connected(self, message=None):
        self.status_update('CONNECTED')
        self.client.send(messages.MemdumpView(self.memory.view_start, self.memory.view_size))
        self.client.send(messages.DisassemblyView(self.disassembly.view_start, self.disassembly.view_size))

    def receive_register_state(self, message):
        #We'll do 3 columns
        view = self.registers
        lines = [list() for i in xrange(view.num_lines)]
        col_width = view.width/3
        for i,reg in enumerate(message.registers):
            lines[i%len(lines)].append( ('%3s : %08x' % (register_name(i),reg)).ljust(col_width) )

        pos = len(message.registers)
        lines[pos%len(lines)].append( ('%5s : %8s' % ('MODE',mode_names[message.mode]) ))
        lines[(pos+1)%len(lines)].append( ('%5s : %08x' % ('PC',message.pc) ))
        self.registers.delete('1.0',Tkinter.END)
        for i,line in enumerate(lines):
            line = ''.join(line).ljust(view.width)
            view.insert('%d.0' % (i+1), line + '\n')



def main():
    root = Tkinter.Tk()
    root.tk_setPalette(background='black',
                       highlightbackground='lawn green')
    app = Application(master=root)
    with messages.Client('localhost', 0x4141, callback=app.message_handler) as client:
        print client
        app.client = client
        app.mainloop()
    root.destroy()

if __name__ == '__main__':
    main()
