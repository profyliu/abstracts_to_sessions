import pandas as pd
import numpy as np
import argparse
ap = argparse.ArgumentParser()
ap.add_argument("-r", "--reslim", type=int, default=900, help="time limit in seconds")
ap.add_argument("-i", "--input", type=str, default="Session Planning LSC.xlsx", help="input Excel file")
ap.add_argument("-s", "--solver", type=str, default="cplex", help="GAMS solver name")
ap.add_argument("-w", "--warmstart", type=int, default=0, help="0 cold start, 1 warm start from sol.gdx")
ap.add_argument("-t", "--threads", type = int, default = 1, help="number of parallel threads to use")
args = vars(ap.parse_args())

data = pd.read_excel(args['input'])

IDs = data['Abstract #']
titles = data['Title']
keywords = data['Keywords']
abstracts = data['Abstract Summary']

all_title_words = []
for i in range(len(titles)):
    all_title_words = all_title_words + titles[i].split() + keywords[i].split()
# remove duplicates
all_title_words = list(dict.fromkeys(all_title_words))
# define stop words
stop_words = ['a', 'an', 'and', 'the', 'by', 'in', 'on', 'for', 'about', 'we', 'can', 'is', 'are', 'it', 'or', 'of', 'at', 
              'to', 'how', 'up', 'was', 'were', 'so', 'this', 'that', 'there', 'be', 'some', 'very', 'every', 
              'all', 'which', 'here', 'where', 'who', '-', 'under', 'with', 'without','same', 'one', 'based','using',
              'study', 'problem', 'address', 'model', 'case']
# remove stop words, keep only stem of long words
title_words = []
for i in range(len(all_title_words)):
    this_word = all_title_words[i].lower()
    if this_word not in stop_words and len(this_word) > 3:
        if len(this_word) > 5:
            title_words = title_words + [this_word[0:5]]
        else:
            title_words = title_words + [this_word]
# dedup one more time
title_words = list(dict.fromkeys(title_words))

# Compute title word frequency
title_words_freq = [0 for ij in range(len(title_words))]
for i in range(len(titles)):
    this_doc = (titles[i] + keywords[i] + abstracts[i]).split()
    this_doc_words = []
    for j in range(len(this_doc)):
        this_word = this_doc[j].lower()
        if this_word not in stop_words and len(this_word) > 3:
            if len(this_word) > 5:
                this_word = this_word[0:5]
            this_doc_words = this_doc_words + [this_word]
    this_doc_words = list(dict.fromkeys(this_doc_words))  # dedup
    for j in range(len(title_words)):
        for k in range(len(this_doc_words)):
            if this_doc_words[k] == title_words[j]:
                title_words_freq[j] += 1

# Filter out low and high frequency title words
stem_freq = pd.DataFrame({"stem":title_words, "freq":title_words_freq})
stem_freq = stem_freq.sort_values(by = "freq",ascending=False)
#stem_freq = stem_freq.loc[stem_freq['freq'].isin([i for i in range(3,22)])]
stem_freq.to_csv("stem_freq_all.csv")

'''
title_words = [i for i in stem_freq['stem']]
feature_matrix = np.zeros((len(titles),len(title_words)))
feature_weight = [1 for i in range(len(title_words))]

# Give higher weight to picked words
stem_pick = pd.read_csv("stem_freq_all_pick.csv")
picked_words = list(stem_pick.loc[stem_pick['pick'] == 1, 'stem'])
for i in range(len(title_words)):
    if title_words[i] in picked_words:
        feature_weight[i] = 5
'''

# Hand pick key words
stem_pick = pd.read_csv("stem_freq_all_pick.csv")
title_words = list(stem_pick.loc[stem_pick['pick'] == 1, 'stem'])
feature_matrix = np.zeros((len(titles),len(title_words)))
feature_weight = [1 for i in range(len(title_words))]

# Compute the whole feature matrix
for i in range(len(titles)):
    this_doc = (titles[i] + keywords[i] + abstracts[i]).split()
    this_doc_words = []
    for j in range(len(this_doc)):
        this_word = this_doc[j].lower()
        if this_word not in stop_words and len(this_word) > 3:
            if len(this_word) > 5:
                this_word = this_word[0:5]
            this_doc_words = this_doc_words + [this_word]
    this_doc_words = list(dict.fromkeys(this_doc_words))  # dedup
    for j in range(len(title_words)):
        for k in range(len(this_doc_words)):
            if this_doc_words[k] == title_words[j]:
                feature_matrix[i,j] = 1

# Compute the doc-doc similarity matrix
simi_matrix = np.zeros((len(titles),len(titles)))
for i in range(len(titles)):
    for j in range(i+1, len(titles)-1):
        sij = np.multiply(feature_matrix[i,:], feature_matrix[j,:])
        sij = np.multiply(sij, feature_weight)
        simi_matrix[i,j] = np.sum(sij)

# Now that we have the doc-to-doc similarity matrix, we can run an optimization model to group abstracts 
# Constraints: each session must have no more than 4 talks, fill all four slots if possible
# Each talk must be assigned to a session
# The score of a session is the sum of the pairwise similarity values of all talks placed in the session
# Objective: maximize the total score of the track (all sessions)
# This is a binary quadratic assignment problem.

# How much time do we give the solver?
reslim = args['reslim']
solver = args['solver']

# Generate a GAMS model
with open("assign.gms","w") as f:
    f.write("option reslim = " + str(reslim) + ";\n")
    f.write("option miqcp = " + solver + ";\n")
    f.write("option threads = " + str(args['threads']) + ";\n")
    f.write("set i /1*" + str(len(titles)) +"/;\n")
    f.write("set g /1*" + str(int(np.ceil(len(titles)/ 4))) + "/;\n")
    f.write("alias(i,j,k);\nparameter s(i,j);\n")
    for i in range(len(titles)):
        for j in range(i+1, len(titles)-1):
            f.write("s('" + str(i+1) + "','" + str(j+1) + "') = " + str(simi_matrix[i,j]) + ";\n")
    f.write('''
binary variables
x(i,g) 1 if talk i is in session g
;
variable group_score(g);
variable total_score;
equations
    eq_group_size(g) each group has at most four talks
    eq_score(g) calculate group score
    eq_place(i) every talk must be placed in a session
    eq_obj calculate objective value
;
eq_group_size(g)..
    sum(i, x(i,g)) =l= 4;
eq_place(i)..
    sum(g, x(i,g)) =e= 1;
eq_score(g)..
    group_score(g) =e= sum((i,j)$(ord(i)<ord(j)), s(i,j)*x(i,g)*x(j,g));
eq_obj..
    total_score =e= sum(g, group_score(g));
model assign /eq_group_size, eq_place, eq_score, eq_obj/;
parameter x_sol(i,g);
    ''')
    f.write("\n")
    if args['warmstart'] == 1:
        f.write('''
execute_load 'sol.gdx' x_sol;
x.l(i,g) = x_sol(i,g);
        ''')
        f.write("\n")
        f.write("$onEcho > " + solver + ".opt\n")
        f.write('''
mipstart 1
$offEcho
assign.optfile=1;
        ''')
        f.write("\n")
    f.write('''
solve assign maximize total_score using miqcp;
parameter result(i);
loop((i,g)$x.l(i,g),
    result(i) = ord(g);
);
display result;

file f /'sol.txt'/;
put f;
loop(i,
    put (ord(i)-1):0:0 ' ' (result(i)-1):0:0 /;
)
putclose;
x_sol(i,g) = x.l(i,g);
execute_unload 'sol.gdx' x_sol;
    ''')
    f.write("\n")

# Run the GAMS model
import subprocess
subprocess.run(["gams", "assign.gms"])

# Read the GAMS solution (titleID sessionID)
sol = pd.read_csv("sol.txt", sep = " ", header = None)

# Extract the common stems in each session
n_sessions = int(np.ceil(len(titles)/ 4))
stem2 = []  # stems that are in two or more abstracts
stem3 = []  # stems that are in three or more abstracts
for g in range(n_sessions):
    ids = []
    for i in range(len(titles)):
        if sol.iloc[i,1] == g:
            ids += [i]
    this_session_features = feature_matrix[ids,:]
    n = this_session_features.shape[0]
    common2_idx = []
    common3_idx = []
    for j in range(len(title_words)):
        freq = 0
        for k in range(n):
            if this_session_features[k,j] == 1:
                freq += 1;
        if freq >= 2:
            common2_idx += [j]
        if freq >= 3:
            common3_idx += [j]
    common_stem2 = ' '.join([title_words[i] for i in common2_idx])
    common_stem3 = ' '.join([title_words[i] for i in common3_idx])
    stem2 += [common_stem2]
    stem3 += [common_stem3]

# Write the session summary
session_summary = pd.DataFrame({"Session ID":[i for i in range(n_sessions)], "stem2":stem2, "stem3":stem3})
session_summary.to_csv("session_summary.csv")

# Write assignment result to CSV
res = pd.DataFrame({"Abstract ID":IDs, "Session ID":sol.iloc[:,1]})
res.to_csv("result.csv")