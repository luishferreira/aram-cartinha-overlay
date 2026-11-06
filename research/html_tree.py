from html.parser import HTMLParser

class Node:
    def __init__(self,tag='',attrs=None,parent=None):
        self.tag=tag;self.attrs=dict(attrs or []);self.children=[];self.parent=parent
    def text(self):
        return ' '.join(' '.join(c.text() if isinstance(c,Node) else c for c in self.children).split())
    def find(self,tag=None,predicate=None):
        for c in self.children:
            if isinstance(c,Node):
                if (tag is None or c.tag==tag) and (predicate is None or predicate(c)):
                    yield c
                yield from c.find(tag,predicate)

class Tree(HTMLParser):
    VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self,text):
        super().__init__();self.root=Node();self.current=self.root;self.feed(text)
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs,self.current);self.current.children.append(n)
        if tag not in self.VOID:self.current=n
    def handle_startendtag(self,tag,attrs):
        self.current.children.append(Node(tag,attrs,self.current))
    def handle_endtag(self,tag):
        n=self.current
        while n.parent and n.tag!=tag:n=n.parent
        if n.tag==tag:self.current=n.parent or self.root
    def handle_data(self,data):
        self.current.children.append(data)

if __name__=='__main__':
    from pathlib import Path
    for name in ['aramgg-augments','aramkit-augments','arammayhem-augments']:
        tree=Tree(Path(f'research/external-snapshots/{name}.html').read_text('utf-8')).root
        rows=list(tree.find('tr'))
        print(name,'rows',len(rows))
        for row in rows[:4]:
            print('ROW',row.attrs,row.text()[:600],[(a.text()[:70],a.attrs.get('href')) for a in row.find('a')][:5])
        if not rows:
            nodes=list(tree.find(predicate=lambda n: 'data-tier' in n.attrs or 'data-name' in n.attrs))
            for n in nodes[:3]:print(n.tag,n.attrs,n.text()[:250])
