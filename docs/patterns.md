# CodeCompass Pattern List

The fixed pattern list for R-01. The descriptions are the text of the beginner hint in R-27, so they say when a pattern applies without giving a solution. Family groups related patterns on the dashboard's pattern map. Tier shows how much ground a pattern covers, not how hard it is, and sets how quickly its score rises: 40% per attempt for narrow, 30% for normal, and 20% for broad. Core patterns are always active. Advanced patterns are off until the user turns them on or marks one as a target (R-32).

The last two columns show where each pattern comes from. "Interview lists" names the matching NeetCode or LeetCode topic. "Codeforces tags" names the tags to map from when building the catalog or looking up a problem (R-33, R-35). A dash means there is no direct match.

## Core patterns

| # | Pattern | Tier | Family | Description | Interview lists | Codeforces tags |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Arrays and Hashing | Normal | Arrays and strings | Use a hash map or set to count items or look them up in constant time. | NeetCode: Arrays & Hashing | - |
| 2 | Prefix Sums | Narrow | Arrays and strings | Precompute running totals so range totals can be answered quickly. | LeetCode: Prefix Sum | - |
| 3 | Two Pointers | Normal | Arrays and strings | Move two indices through a sequence, often from both ends, to avoid checking every pair. | NeetCode: Two Pointers | two pointers |
| 4 | Sliding Window | Normal | Arrays and strings | Keep a contiguous range and grow or shrink it as you scan. | NeetCode: Sliding Window | two pointers |
| 5 | Stack | Normal | Stacks, lists, and heaps | Use last-in, first-out order to track nested or unfinished items. | NeetCode: Stack | data structures |
| 6 | Monotonic Stack and Queue | Normal | Stacks, lists, and heaps | Keep items in sorted order to find the next greater or smaller value, or a window's extreme. | NeetCode: Stack | data structures |
| 7 | Linked List | Normal | Stacks, lists, and heaps | Rewire nodes in place, often with a dummy head or fast and slow pointers. | NeetCode: Linked List | - |
| 8 | Binary Search | Normal | Searching and ordering | Halve a sorted range or a yes-or-no answer space on each step. | NeetCode: Binary Search | binary search |
| 9 | Sorting | Normal | Searching and ordering | Put items in a useful order first so the rest of the problem becomes simpler. | LeetCode: Sorting | sortings |
| 10 | Intervals | Normal | Searching and ordering | Sort ranges by an endpoint, then merge them or check for overlaps. | NeetCode: Intervals | greedy, sortings |
| 11 | Heap | Normal | Stacks, lists, and heaps | Use a priority queue to get the current smallest or largest item repeatedly. | NeetCode: Heap / Priority Queue | data structures |
| 12 | Tree Traversal | Normal | Trees | Visit nodes depth-first or level by level, combining results from children. | NeetCode: Trees | trees, dfs and similar |
| 13 | Binary Search Trees | Narrow | Trees | Use the ordering of left and right subtrees to guide the search. | NeetCode: Trees | trees |
| 14 | Trie | Narrow | Trees | Store strings in a prefix tree to share common prefixes. | NeetCode: Tries | strings, data structures |
| 15 | Backtracking and Brute Force | Normal | Recursion and DP | Try the possible choices, undoing each one and cutting off dead ends. | NeetCode: Backtracking | brute force |
| 16 | Graph Traversal | Broad | Graphs | Explore connected nodes with BFS or DFS while tracking what has been visited. | NeetCode: Graphs | graphs, dfs and similar |
| 17 | Topological Sort | Narrow | Graphs | Order the nodes of a directed graph so dependencies come first. | NeetCode: Graphs | graphs |
| 18 | Union-Find | Narrow | Graphs | Merge groups and check whether two items are in the same group. | NeetCode: Graphs | dsu |
| 19 | Shortest Paths | Normal | Graphs | Find minimum-cost routes through a weighted graph. | NeetCode: Advanced Graphs | shortest paths |
| 20 | Minimum Spanning Tree | Narrow | Graphs | Connect all nodes at the lowest total edge cost. | NeetCode: Advanced Graphs | graphs, dsu |
| 21 | 1-D Dynamic Programming | Broad | Recursion and DP | Build an answer from smaller answers along a single index. | NeetCode: 1-D Dynamic Programming | dp |
| 22 | 2-D Dynamic Programming | Broad | Recursion and DP | Build an answer from smaller answers over two indices, such as a grid or two strings. | NeetCode: 2-D Dynamic Programming | dp |
| 23 | Greedy | Broad | Searching and ordering | Make the locally best choice at each step, after checking that doing so is safe. | NeetCode: Greedy | greedy |
| 24 | Bit Manipulation | Normal | Math and bits | Use binary operations on the bits of a number. | NeetCode: Bit Manipulation | bitmasks |
| 25 | Math | Normal | Math and bits | Find a formula or numeric property that replaces simulating the process. | NeetCode: Math & Geometry | math |
| 26 | Strings | Normal | Arrays and strings | Process characters directly, for example by parsing or comparing. | LeetCode: String | strings |
| 27 | Simulation and Implementation | Normal | Implementation and design | Carry out the described process carefully, step by step. | LeetCode: Simulation | implementation, schedules |
| 28 | Data Structure Design | Normal | Implementation and design | Combine structures to support the required operations efficiently. | LeetCode: Design | data structures |

## Advanced patterns

| # | Pattern | Tier | Family | Description | Interview lists | Codeforces tags |
| --- | --- | --- | --- | --- | --- | --- |
| 29 | Number Theory | Normal | Math and bits | Use divisibility, primes, greatest common divisors, or modular arithmetic. | - | number theory |
| 30 | Chinese Remainder Theorem | Narrow | Math and bits | Combine conditions on remainders for coprime or related moduli. | - | chinese remainder theorem |
| 31 | Combinatorics | Normal | Math and bits | Count arrangements with formulas rather than listing them. | - | combinatorics |
| 32 | Probability and Expected Value | Normal | Math and bits | Calculate chances or averages, often using linearity of expectation. | - | probabilities |
| 33 | Game Theory | Normal | Math and bits | Reason about winning and losing positions under optimal play. | - | games |
| 34 | Geometry | Normal | Math and bits | Work with points, lines, and shapes, often using cross products. | NeetCode: Math & Geometry | geometry |
| 35 | Matrices and Matrix Exponentiation | Normal | Math and bits | Express a repeated transition as a matrix, then raise it to a power. | - | matrices |
| 36 | FFT and NTT | Normal | Math and bits | Multiply polynomials or compute convolutions faster than quadratic time. | - | fft |
| 37 | Constructive Algorithms | Broad | Implementation and design | Build any valid answer directly from a pattern you can prove works. | - | constructive algorithms |
| 38 | Divide and Conquer | Normal | Searching and ordering | Split the input, solve each part, and combine the results. | LeetCode: Divide and Conquer | divide and conquer |
| 39 | Meet in the Middle | Narrow | Searching and ordering | Split the search space in half and combine the two lists of results. | - | meet-in-the-middle |
| 40 | Ternary Search | Narrow | Searching and ordering | Narrow in on the peak or valley of a function with a single turning point. | - | ternary search |
| 41 | Segment Tree and Fenwick Tree | Normal | Trees | Answer range queries and handle updates in logarithmic time. | LeetCode: Segment Tree, Binary Indexed Tree | data structures |
| 42 | Tree DP | Normal | Recursion and DP | Compute a value for each subtree from the values of its children. | - | trees, dp |
| 43 | Bitmask DP | Normal | Recursion and DP | Use a set of chosen items, stored as bits, as the dynamic programming state. | LeetCode: Bitmask | bitmasks, dp |
| 44 | Lowest Common Ancestor and Tree Queries | Normal | Trees | Answer questions about paths between tree nodes after preprocessing. | - | trees |
| 45 | String Hashing | Narrow | Arrays and strings | Compare substrings quickly using rolling or polynomial hashes. | LeetCode: Rolling Hash | hashing |
| 46 | String Matching | Normal | Arrays and strings | Find occurrences of a pattern using prefix information, as in KMP or the Z-function. | LeetCode: String Matching | strings |
| 47 | Suffix Structures | Normal | Arrays and strings | Use suffix arrays or automata to answer questions about substrings. | LeetCode: Suffix Array | string suffix structures |
| 48 | Strongly Connected Components and Bridges | Normal | Graphs | Find a graph's tightly linked groups or its critical connections. | - | graphs, dfs and similar |
| 49 | Max Flow and Min Cut | Normal | Graphs | Model limits as edge capacities and find the most that can pass through. | - | flows |
| 50 | Bipartite Matching | Narrow | Graphs | Pair items from two groups so as many as possible are matched. | - | graph matchings |
| 51 | 2-SAT | Narrow | Graphs | Express either-or constraints as a graph on true and false choices. | - | 2-sat |
| 52 | Interactive Problems | Normal | Implementation and design | Ask the judge questions and narrow down the answer within a query limit. | - | interactive |
| 53 | Expression Parsing | Normal | Implementation and design | Evaluate or process nested expressions according to their structure. | - | expression parsing |

## Codeforces tags that need care

- **Not mapped:** `*special` and `communication`, which describe the problem format or contest rather than a technique.
- **Too broad to map automatically:** `data structures`, `graphs`, `dfs and similar`, `math`, `trees`, `strings`, `dp`, and `two pointers` each match more than one pattern, so these problems need a person to choose the pattern.
- **Pairs:** when picking catalog problems, Tree DP, Bitmask DP, and Minimum Spanning Tree need both of their listed tags at once. `docs/rules.md` (Catalog sources) gives the full picking rule, including which pattern a shared tag is picked for.
