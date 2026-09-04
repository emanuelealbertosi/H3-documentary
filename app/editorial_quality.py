"""Deterministic checks for repeated scene ideas and narration."""
import difflib,re

STOPWORDS=set("""il lo la i gli le un uno una di del dello della dei degli delle e o a ad da in con su per tra fra che si al alla allo ai agli alle nel nello nella nei negli nelle verso dopo prima come anche più ma poi cui sua suo suoi sue dall dell nell all""".split())


def terms(text):
    return [word for word in re.findall(r"[a-zà-öø-ÿ0-9]+",str(text).casefold()) if word not in STOPWORDS and len(word)>1]


def near_duplicates(rows,text_key):
    """Return pairs whose wording describes substantially the same material."""
    prepared=[]
    for index,row in enumerate(rows):
        words=terms(text_key(row));grams={' '.join(words[i:i+8]) for i in range(max(0,len(words)-7))}
        prepared.append((index,words,' '.join(words),set(words),grams))
    duplicates=[]
    for left in range(len(prepared)):
        ia,wa,sa,set_a,grams_a=prepared[left]
        if len(wa)<5:continue
        for right in range(left+1,len(prepared)):
            ib,wb,sb,set_b,grams_b=prepared[right]
            if len(wb)<5:continue
            overlap=len(set_a & set_b);jaccard=overlap/max(1,len(set_a | set_b))
            sequence=difflib.SequenceMatcher(None,sa,sb).ratio()
            if grams_a & grams_b or sequence>=.68 or (overlap>=5 and jaccard>=.40 and sequence>=.44):
                duplicates.append((ia,ib,round(max(sequence,jaccard),2)))
    return duplicates
