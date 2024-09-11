from pathlib import Path
from collections import Counter
words = Counter()

mega_file_list: list = list(Path(".").rglob("*.txt"))

word_count = {}
for file in mega_file_list:
    for line in open(file):
        words.update(line.lower().split())

for w,c in words.most_common(500):
    print("{w:20} {c:10}".format(w=w,c=c))
