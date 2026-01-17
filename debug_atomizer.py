import spacy

nlp = spacy.load("en_core_web_sm")
text = "The polling stations opened at 7 AM and Mayor Smith is running for re-election."
doc = nlp(text)

print(f"{'Token':<12} {'Dep':<10} {'Head':<12} {'Head Dep':<10} {'Head Pos':<10}")
print("-" * 60)
for token in doc:
    print(f"{token.text:<12} {token.dep_:<10} {token.head.text:<12} {token.head.dep_:<10} {token.head.pos_:<10}")
