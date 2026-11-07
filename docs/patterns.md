# CodeCompass Pattern List

The fixed pattern list for R-01. The descriptions are the text of the beginner hint in R-27, so they say when a pattern applies without giving a solution. Tier shows how much ground a pattern covers, not how hard it is, and sets how quickly its score rises: 40% per attempt for narrow, 30% for normal, and 20% for broad. Core patterns are always active. Advanced patterns are off until the user turns them on or marks one as a target (R-32).

The last two columns show where each pattern comes from. "Interview lists" names the matching NeetCode or LeetCode topic. "Codeforces tags" names the tags to map from when building the catalog or looking up a problem (R-33, R-35). A dash means there is no direct match.

## Core patterns

| # | Pattern | Tier | Description | Interview lists | Codeforces tags |
| --- | --- | --- | --- | --- | --- |
| 1 | Arrays and Hashing | Normal | Use a hash map or set to count items or look them up in constant time. | NeetCode: Arrays & Hashing | - |
| 2 | Prefix Sums | Narrow | Precompute running totals so range totals can be answered quickly. | LeetCode: Prefix Sum | - |
| 3 | Two Pointers | Normal | Move two indices through a sequence, often from both ends, to avoid checking every pair. | NeetCode: Two Pointers | two pointers |
| 4 | Sliding Window | Normal | Keep a contiguous range and grow or shrink it as you scan. | NeetCode: Sliding Window | two pointers |
| 5 | Stack | Normal | Use last-in, first-out order to track nested or unfinished items. | NeetCode: Stack | data structures |
| 6 | Monotonic Stack and Queue | Normal | Keep items in sorted order to find the next greater or smaller value, or a window's extreme. | NeetCode: Stack | data structures |
| 7 | Linked List | Normal | Rewire nodes in place, often with a dummy head or fast and slow pointers. | NeetCode: Linked List | - |
| 8 | Binary Search | Normal | Halve a sorted range or a yes-or-no answer space on each step. | NeetCode: Binary Search | binary search |
| 9 | Sorting | Normal | Put items in a useful order first so the rest of the problem becomes simpler. | LeetCode: Sorting | sortings |
| 10 | Intervals | Normal | Sort ranges by an endpoint, then merge them or check for overlaps. | NeetCode: Intervals | greedy, sortings |
| 11 | Heap | Normal | Use a priority queue to get the current smallest or largest item repeatedly. | NeetCode: Heap / Priority Queue | data structures |
| 12 | Tree Traversal | Normal | Visit nodes depth-first or level by level, combining results from children. | NeetCode: Trees | trees, dfs and similar |
| 13 | Binary Search Trees | Narrow | Use the ordering of left and right subtrees to guide the search. | NeetCode: Trees | trees |
| 14 | Trie | Narrow | Store strings in a prefix tree to share common prefixes. | NeetCode: Tries | strings, data structures |
| 15 | Backtracking and Brute Force | Normal | Try the possible choices, undoing each one and cutting off dead ends. | NeetCode: Backtracking | brute force |
| 16 | Graph Traversal | Broad | Explore connected nodes with BFS or DFS while tracking what has been visited. | NeetCode: Graphs | graphs, dfs and similar |
| 17 | Topological Sort | Narrow | Order the nodes of a directed graph so dependencies come first. | NeetCode: Graphs | graphs |
| 18 | Union-Find | Narrow | Merge groups and check whether two items are in the same group. | NeetCode: Graphs | dsu |
| 19 | Shortest Paths | Normal | Find minimum-cost routes through a weighted graph. | NeetCode: Advanced Graphs | shortest paths |
| 20 | Minimum Spanning Tree | Narrow | Connect all nodes at the lowest total edge cost. | NeetCode: Advanced Graphs | graphs, dsu |
| 21 | 1-D Dynamic Programming | Broad | Build an answer from smaller answers along a single index. | NeetCode: 1-D Dynamic Programming | dp |
| 22 | 2-D Dynamic Programming | Broad | Build an answer from smaller answers over two indices, such as a grid or two strings. | NeetCode: 2-D Dynamic Programming | dp |
| 23 | Greedy | Broad | Make the locally best choice at each step, after checking that doing so is safe. | NeetCode: Greedy | greedy |
| 24 | Bit Manipulation | Normal | Use binary operations on the bits of a number. | NeetCode: Bit Manipulation | bitmasks |
| 25 | Math | Normal | Find a formula or numeric property that replaces simulating the process. | NeetCode: Math & Geometry | math |
| 26 | Strings | Normal | Process characters directly, for example by parsing or comparing. | LeetCode: String | strings |
| 27 | Simulation and Implementation | Normal | Carry out the described process carefully, step by step. | LeetCode: Simulation | implementation, schedules |
| 28 | Data Structure Design | Normal | Combine structures to support the required operations efficiently. | LeetCode: Design | data structures |

## Advanced patterns

| # | Pattern | Tier | Description | Interview lists | Codeforces tags |
| --- | --- | --- | --- | --- | --- |
| 29 | Number Theory | Normal | Use divisibility, primes, greatest common divisors, or modular arithmetic. | - | number theory |
| 30 | Chinese Remainder Theorem | Narrow | Combine conditions on remainders for coprime or related moduli. | - | chinese remainder theorem |
| 31 | Combinatorics | Normal | Count arrangements with formulas rather than listing them. | - | combinatorics |
| 32 | Probability and Expected Value | Normal | Calculate chances or averages, often using linearity of expectation. | - | probabilities |
| 33 | Game Theory | Normal | Reason about winning and losing positions under optimal play. | - | games |
| 34 | Geometry | Normal | Work with points, lines, and shapes, often using cross products. | NeetCode: Math & Geometry | geometry |
| 35 | Matrices and Matrix Exponentiation | Normal | Express a repeated transition as a matrix, then raise it to a power. | - | matrices |
| 36 | FFT and NTT | Normal | Multiply polynomials or compute convolutions faster than quadratic time. | - | fft |
| 37 | Constructive Algorithms | Broad | Build any valid answer directly from a pattern you can prove works. | - | constructive algorithms |
| 38 | Divide and Conquer | Normal | Split the input, solve each part, and combine the results. | LeetCode: Divide and Conquer | divide and conquer |
| 39 | Meet in the Middle | Narrow | Split the search space in half and combine the two lists of results. | - | meet-in-the-middle |
| 40 | Ternary Search | Narrow | Narrow in on the peak or valley of a function with a single turning point. | - | ternary search |
| 41 | Segment Tree and Fenwick Tree | Normal | Answer range queries and handle updates in logarithmic time. | LeetCode: Segment Tree, Binary Indexed Tree | data structures |
| 42 | Tree DP | Normal | Compute a value for each subtree from the values of its children. | - | trees, dp |
| 43 | Bitmask DP | Normal | Use a set of chosen items, stored as bits, as the dynamic programming state. | LeetCode: Bitmask | bitmasks, dp |
| 44 | Lowest Common Ancestor and Tree Queries | Normal | Answer questions about paths between tree nodes after preprocessing. | - | trees |
| 45 | String Hashing | Narrow | Compare substrings quickly using rolling or polynomial hashes. | LeetCode: Rolling Hash | hashing |
| 46 | String Matching | Normal | Find occurrences of a pattern using prefix information, as in KMP or the Z-function. | LeetCode: String Matching | strings |
| 47 | Suffix Structures | Normal | Use suffix arrays or automata to answer questions about substrings. | LeetCode: Suffix Array | string suffix structures |
| 48 | Strongly Connected Components and Bridges | Normal | Find a graph's tightly linked groups or its critical connections. | - | graphs, dfs and similar |
| 49 | Max Flow and Min Cut | Normal | Model limits as edge capacities and find the most that can pass through. | - | flows |
| 50 | Bipartite Matching | Narrow | Pair items from two groups so as many as possible are matched. | - | graph matchings |
| 51 | 2-SAT | Narrow | Express either-or constraints as a graph on true and false choices. | - | 2-sat |
| 52 | Interactive Problems | Normal | Ask the judge questions and narrow down the answer within a query limit. | - | interactive |
| 53 | Expression Parsing | Normal | Evaluate or process nested expressions according to their structure. | - | expression parsing |

## Codeforces tags that need care

- **Not mapped:** `*special` and `communication`, which describe the problem format or contest rather than a technique.
- **Too broad to map automatically:** `data structures`, `graphs`, `dfs and similar`, `math`, `trees`, `strings`, `dp`, and `two pointers` each match more than one pattern, so these problems need a person to choose the pattern.
