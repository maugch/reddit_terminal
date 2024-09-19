from datetime import datetime,UTC
import configparser
from textual.app import App, ComposeResult
from textual import events
from textual.driver import Driver
from textual.widgets import Footer, Label, ListItem, ListView,Header,Markdown,Tree
from textual.screen import ModalScreen,Screen
from textual.containers import Horizontal
from textual.reactive import reactive
from asyncpraw.models import MoreComments

from requests import head as r_head
import asyncpraw
from asyncpraw.models import Submission

from reader import ReaderApp,TextLine,StoryScreen,StatusLabel


class RedditLine(TextLine):
    DEFAULT_CSS = '''
        #sublbl {
            color: yellow;
            
        }
    '''
    #content-align: right center;
    def __init__(self, submission: Submission, shrink=False) -> None:
        super().__init__(shrink = shrink)     

        self.submission = submission
        #self.title = ' {} - {}'.format(submission.score, submission.title.strip())
        self.title = '{}'.format(submission.title.strip())
        self.original_title = self.title
        #self.content_text = self.submission.selftext #+ str(len(self.submission.comments))
    
    @property
    def content_text(self):
        sub = self.submission
        text = sub.selftext
        if not sub.is_self:
            text += '\n' + sub.url
        return text
    
    
    def check_url(self) -> None:
        url = self.submission.url
        r = r_head(url)
        if r.headers['location'] != url :
            redirect_url = r.headers['location']
        else:
            None

    def compose( self ) -> ComposeResult:
        now = datetime.now(UTC)
        created = datetime.fromtimestamp(int(self.submission.created_utc),UTC)
        hours = (now-created).seconds//3600
        sub = 'score: {} submitted:{}hours'.format(self.submission.score,hours)
        yield Label(self.title,shrink=self.shrink,id='lbl')
        yield Label(sub,id='sublbl')


class RedditScreen(StoryScreen):
    
    line : RedditLine = None
    
    def __init__(self, r_line: RedditLine= None):
        super().__init__()
        self.line = r_line
   
    def define_binders(self):
        self.app.binders.append(["q", "back", "Back"])
        self.app.binders.append(["c", 'read_comments',  "open comments"])

class RedditApp(ReaderApp): 
    
    user_agent = 'python:shell-reader:v0.1 (by /u/nrael)'
    reddit = None
    number_of_posts = 20
    last_best = None

    def __init__(self):
        super().__init__()
        self.title = "Reddit Reader"
            
    def load_config(self):
        c_file = 'config.ini'
        config = configparser.ConfigParser()
        cfg = config.read(c_file)
        if len(cfg) == 0:
            self.log('empty config')
            config['Default'] = { 'username':'xxx','password':'xxx','client_id':'xxx','client_secret':'xxx'}
            with open(c_file, 'w') as configfile:
                config.write(configfile)
            return False
        else:
            self.CLIENT_ID = config['Default']['client_id']
            self.CLIENT_SECRET = config['Default']['client_secret']
            self.USERNAME = config['Default']['username']
            self.PASSWORD = config['Default']['password']
        return True

    def on_mount(self) -> None:
        super().on_mount()
        self.binders.append(["r", 'show_post', "Read Post"])
        self.init_reddit()

    def key_enter(self) -> None:
        self.action_show_post()

    def action_show_post(self) -> None:    
        if not self.is_line_selected():
            return
        
        if isinstance(self.selected_line,RedditLine):
            post : Submission = self.selected_line.submission
            if post.is_self:
                new_status = 'text post'
            else:
                new_status = 'url post'
            self.status_text = new_status
        self.push_screen(RedditScreen(self.selected_line).data_bind(ReaderApp.status_text))

    def init_reddit(self) -> None:
        self.reddit = asyncpraw.Reddit(
            client_id=self.CLIENT_ID,
            client_secret=self.CLIENT_SECRET,
            password=self.PASSWORD,
            user_agent=self.user_agent,
            username=self.USERNAME,
        )
        self.binders.append(["l", "load_best", 'load best'])
        self.binders.append(['n',"load_next_best",'load next '+str(self.number_of_posts)])
        
    
    def action_read_comments(self) -> None:
        self.app.read_comments()

    def action_load_best(self) -> None:
        self.log('load best')
        self.header.loading = True
        self.status_text = "Loading Best..."
        self.buffer.clear()
        
        self.run_worker(self.fetch_best(self.number_of_posts),exclusive=True)

    async def fetch_best(self,plimit = 10) -> None:
        if not self.reddit:
            return 
        
        result : list[RedditLine] = []

        if self.last_best is None:
            async for submission in self.reddit.front.best(limit=plimit):
                result.append(RedditLine(submission))
                self.last_best = submission.fullname
                clear_lv = True
        else:
            async for submission in self.reddit.front.best(limit=plimit,params={'after': self.last_best}):
                result.append(RedditLine(submission))
                self.last_best = submission.fullname
                clear_lv = False
            
        self._load_buffer(result,clear_lv=clear_lv)
        self.header.loading = False
        self.status_text = "Loaded"
    

    def action_load_next_best(self) -> None:
        self.log('load next')
        self.header.loading = True
        self.status_text = 'Loading next posts...'

        self.run_worker(self.fetch_best(self.number_of_posts),exclusive=True)
    
    async def fetch_comments(self, submission : Submission):
        
        tree: Tree[dict] = Tree("Comments")
        tree.root.expand()

        #characters = tree.root.add(lbl, expand=True)
        #characters.add_leaf("Paul")

        comments = await submission.comments()
        for top_level_comment in comments:
            if isinstance(top_level_comment, MoreComments):
                tree.root.add('more')
                #replace_more()
            else:
                tree.root.add(top_level_comment.body)
        
        self.query_one("#thecontent").mount(tree)
        

    def read_comments(self) -> None:
        self.log('read comments')
        if self.selected_line and isinstance(self.selected_line,RedditLine):
            submission = self.selected_line.submission
            self.run_worker(self.fetch_comments(submission),exclusive=True)
        
    def watch_selected_line(self) -> None:
        super().watch_selected_line()
        if not self.selected_line:
            return
        if isinstance(self.selected_line,RedditLine):
            sub: Submission = self.selected_line.submission
            status = '{} a: {}'.format(sub.subreddit,sub.author.name)
            self.status_text = status
        
def main():
    
    rr = RedditApp()
    if not rr.load_config():
        print("config empty. please fill it.")
        exit()

    rr.run()
    

if __name__ == '__main__':
    main()