# Use text analytics and optimization to group presentations into sessions

As the primary co-chair of the Logistics and Supply Chain (LSC) track of the IISE 2023 Annual Conference, I was charged with the task of grouping 63 accepted abstracts into 16 sessions (at most 4 abstract presentations per session). Clearly, the grouping should be based on topic similarity. 

The input data include the title, keywords, abstract of each presentation as typed in by the submitting author during the abstract submission process. I also have access to the presenter information and the average score from abstract reviewers, but I chose not to use such information for grouping. 

Here, I made an attempt to code up some rather crude method for extracting features from the input text, based on which I computed the similarity matrix (63 x 63), and then formulated a binary quadratic assignment problem. The optimization problem was written in GAMS. The CPLEX solver was used to solve the problem. It turned out that this MIQCP program (involving 63x16 = 1008 binary variables) was quite challenging to solve. I did not have more patience than waiting 15 minutes for a solution, and there is a large optimality gap (~800%) upon interrupted termination. There must be ways to improve the design and solution algorithm. 

The entire solution process is wrapped in a python script, cluster_abstracts.py

Here is an example: run CPLEX for 900 seconds. 

```bash
python cluster_abstracts.py -r 900
```

The results are written to several CSV files. 

I used the solution as the starting point for doing the actual grouping, which involved lots of manual adjustments. 

