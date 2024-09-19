from platform import system

from textual.app import App, ComposeResult
from textual import events
from textual.css.query import NoMatches
from textual.widgets import Footer, Label, ListItem, ListView,Header,Markdown,Tree
from textual.widget import Widget
from textual.widgets import Placeholder
from textual.screen import ModalScreen,Screen
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.message import Message
from asyncpraw.models import MoreComments
import asyncpraw
from asyncpraw.models import Submission
 
class TextLine(ListItem):
    def __init__(self, title:str = None ,content_text:str = None,shrink=False) -> None:
        super().__init__()
        self.lbl_offset = 0
        self.shrink = shrink
        
        self.title = title
        self.original_title = title
        if content_text:
            self.content_text = content_text
        
    @property
    def content_text(self):
        return self._content_text
    
    @content_text.setter
    def content_text(self,new_val):
        self._content_text = new_val

    def compose( self ) -> ComposeResult:
        yield Label(self.title,shrink=self.shrink,id='lbl')

    def update(self,txt) -> None:
        self.query_one("#lbl",Label).update(txt)

    def scroll(self,direction) -> None:
        if direction == 'right':
            self.lbl_offset+=1
        elif direction == 'left':
            self.lbl_offset-=1
        
        if self.lbl_offset < 0:
            self.lbl_offset =0
            #blink ?
        else:
            txt = self.original_title[self.lbl_offset:]    
            self.query_one("#lbl",Label).update(txt)
        



class ReaderApp(App):
    
    DEFAULT_CSS = """
        Horizontal#footer-outer {
            height: 1;
            dock: bottom;
        }
        Horizonal#footer-inner {
            width: 70%;
        }
        StatusLabel {
            color: yellow;
        }
    """
    
    selected_line : TextLine = reactive(None)
    buffer : list[TextLine] = []
    title : str = "Title"
    binders = []
    old_binders = []
    status_text : str = reactive('')

    def __init__(self):
        super().__init__()
        if system() == "Windows":
            self.is_windows = True
        else:
            self.is_windows = False
        

    def compose(self) -> ComposeResult:
        
        self.header = Header(show_clock=True) 
        yield self.header
        yield ListView(id="listview")
        with Horizontal(id="footer-outer"):
            with Horizontal(id="footer-inner"):
                yield Footer()
            yield StatusLabel('status' ,id="right-label").data_bind(ReaderApp.status_text)
        
    def key_left(self) -> None:
        if self.selected_line:
            self.selected_line.scroll('left')

    def key_right(self) -> None:
        if self.selected_line:
            self.selected_line.scroll('right')

    def action_quit(self) -> None:        
        self.log('bye')
        self.exit()

    def make_bindings(self):
        if self.is_windows:
            self._bindings.keys.clear()
        else:
            self._bindings.key_to_bindings.clear()
        for b in self.binders:
            self.app.bind(b[0],b[1],description=b[2])
        
    
    def on_mount(self) -> None:
        self.binders.append(["q", "quit", "Quit"] )
        self.binders.append(["w", "word_wrap", "Word wrap"])
        self.binders.append(["i", "lorem", "load Lorem Ipsum"])
        self.make_bindings()

    def action_word_wrap(self) -> None:
        lbl = self.selected_line.query_one('#lbl')
        lbl.shrink = not lbl.shrink
        lbl.update(self.selected_line.title)

    def _load_buffer(self,new_list :list[TextLine]= None,clear_lv = True):
        if new_list is not None:
            self.buffer = new_list
        lv : ListView = self.query_one("#listview")
        if clear_lv:
            lv.clear()
        for line in self.buffer:
            lv.append(line)
            #lv.append(ListItem(Label(line.title,shrink=True)))
        
    def action_lorem(self) -> None:
        filename = 'lorem.txt'
        mlist : list [TextLine] = []
        temp_list = []
        temp_list_text = ''
        with open(filename) as file:
            for line in file:
                temp_list.append(line.strip())
        temp_list_text = ''.join(temp_list)
        for line in temp_list:
            mlist.append(TextLine(line,temp_list_text))
        
        self._load_buffer(mlist,clear_lv=True)
    
    def on_key(self, event: events.Key) -> None:
        if event.key.isdecimal():
            None
        else:
            None

    def on_list_view_highlighted(self,event: ListView.Highlighted ) -> None:
        if event.item:
            if isinstance(event.item,TextLine):
                self.selected_line = event.item
            else:
                self.log("BUG!!!!!!!!!!!!!")

    def is_line_selected(self) -> None:
        if self.selected_line:
            return True
        return False
    
    def watch_selected_line(self) -> None:
        if not self.selected_line:
            return
        self.status_text = 'text line'
            
class StatusLabel(Label):

    status_text = reactive("Status Text")
    
    def watch_status_text(self) -> None:
        self.update(self.status_text)



class StoryScreen(Screen):
    
    DEFAULT_CSS = """
        .title {
            content-align: center middle;
            width: 100%;
        }
        Horizontal#footer-outer {
            height: 1;
            dock: bottom;
        }
        Horizonal#footer-inner {
            width: 70%;
        }
        
        StatusLabel {
            color: yellow;
        }
       """
    
    line : TextLine = None
    status_text : str = reactive('')

    def __init__(self) -> None:
        super().__init__(id="storyscreen")
        self.swap_binders()        
        self.app.binders.clear()
        self.define_binders()        
        self.make_bindings()

    def compose(self) -> ComposeResult:
        yield Label('', id="title",classes='title')
        yield Markdown(self.line.content_text,id='thecontent')
        with Horizontal(id="footer-outer"):
            with Horizontal(id="footer-inner"):
                yield Footer(id="thefooter")
            yield StatusLabel('b',id="right-label").data_bind(StoryScreen.status_text)

    def define_binders(self):
        self.app.binders.append(["q", "back", "Back"])

    def action_back(self) -> None:
        #self.binders.append(["q", "app.pop_screen", "Back"])
        self.dismiss(True)

    def make_bindings(self):
        self.app.make_bindings()

    def swap_binders(self) -> None:
        self.app.old_binders , self.app.binders = self.app.binders , self.app.old_binders

    def on_unmount(self) -> None:
        self.swap_binders()
        self.make_bindings()

    def key_up(self) -> None:
        self.scroll_up()

    def key_down(self) -> None:
        self.scroll_down()
