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

class Application(Tkinter.Frame):
    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(*args, **kwargs)
        self.stopped = False

    def stop(self):
        self.stopped = True
        self.stop_button['text'] = 'resume'
        self.stop_button['command'] = self.resume
        self.disconnected()

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
        self.disconnected()

    def message_handler(self, message):
        print 'got client message',message

    def disconnected(self):
        """Update the views to show that we're disconnected"""
        self.disassembly.delete('1.0',Tkinter.END)
        for i in xrange(self.disassembly.num_lines):
            if i == self.disassembly.num_lines/2:
                content = '*** DISCONNECTED ***'.center(self.disassembly.width)
            else:
                content = ' '*self.disassembly.width
            self.disassembly.insert('%d.0' % (i+1), content + '\n')

    def __init__(self, master=None):
        Tkinter.Frame.__init__(self, master)
        self.pack()
        self.createWidgets()



def main():
    root = Tkinter.Tk()
    root.tk_setPalette(background='black',
                       highlightbackground='lawn green')
    app = Application(master=root)
    with messages.Client('localhost', 0x4141, callback=app.message_handler) as client:
        app.client = client
        app.mainloop()
    root.destroy()

if __name__ == '__main__':
    main()