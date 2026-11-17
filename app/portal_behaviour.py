"""本地业务页面交互。"""

def detail_fragment(item):
    return '<select id="category"><option>手作</option><option>食饮</option></select><input id="attachment" type="file"><button id="draft">保存演练草稿</button><output id="draft-state"></output><script>document.querySelector(\'#category\').onchange=()=>document.querySelector(\'#draft-state\').textContent=\'材料待核对\';document.querySelector(\'#draft\').onclick=()=>{sessionStorage.setItem(\'stall-category\',document.querySelector(\'#category\').value);document.querySelector(\'#draft-state\').textContent=\'草稿：\'+sessionStorage.getItem(\'stall-category\')};</script>'
