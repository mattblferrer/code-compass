# CodeCompass Pattern Resources

The curated guides for R-59, one list per pattern in the order of `docs/patterns.md`. Each line gives the audience, the site, and the guide, in the order the pattern's page shows them: interview guides first for core patterns, competitive ones first for advanced patterns, then any tricks. "Needs account" marks a site that asks for a free sign-in. A pattern with no entries shows only the user's own links.

## What gets listed

- **Free to read.** Paid courses and pages behind a paywall are left out. A free lesson on a site that also sells a course is allowed if the lesson itself reads in full without paying.
- **Teaches the pattern.** An explanation of when and how the pattern applies, preferably with worked examples or practice problems. A bare problem statement does not count.
- **At most six per pattern**, choosing the clearest over the most complete.
- **Tricks.** A guide whose main topic is something else but that teaches a technique useful for the pattern (for example, a sparse table for prefix sums, or the Euler tour for tree queries) is marked "Trick" and listed after the pattern's main guides.
- **Audience.** "Interview" is written for coding interviews or general learning. "Competitive" is written for contests and usually goes further.

Links were checked by opening them on 2026-11-22. Entries marked "listed" were read from the site's own index; the page itself was not opened. Codeforces and LeetCode block automated checks, so the author checked their pages by hand on the same day. Their entries link to the course or catalog page and name the lesson or card to open there, because the individual lesson and card addresses have not been checked. A maintainer script run by hand (not part of the app, which never fetches these links, R-03) reports links that stop working.

## Sites

| Site | Address | Notes |
| --- | --- | --- |
| USACO Guide | https://usaco.guide/ | Free, no account. Modules by division, each with practice problems. |
| cp-algorithms | https://cp-algorithms.com/ | Free, no account, CC BY-SA. The standard reference for contest algorithms. |
| Hello Interview | https://www.hellointerview.com/learn/code | Lesson pages free without an account; some problem pages are premium and are not listed. |
| Tech Interview Handbook | https://techinterviewhandbook.org/algorithms/introduction | Free. A study cheatsheet per data structure, with corner cases and practice questions. |
| VisuAlgo | https://visualgo.net/ | Free animated lectures. A few answer slides are kept for lecturers. |
| AlgoMonster | https://algo.monster/ | Sells a course; only lessons confirmed free are listed. Some free lessons need an account. |
| Codeforces EDU | https://codeforces.com/edu/course/2 | ITMO Academy pilot course: lessons with practice problems. Needs account. |
| Codeforces blog | https://codeforces.com/blog/ | Tutorials by contest authors. Free, no account. |
| LeetCode Explore | https://leetcode.com/explore/learn/ | Interactive cards per data structure. Needs account. |
| javascript.info | https://javascript.info/ | Free JavaScript tutorial. |
| MDN Web Docs | https://developer.mozilla.org/ | Free JavaScript reference. |

## Core patterns

### 1. Arrays and Hashing
1. Interview · Tech Interview Handbook · [Hash table](https://techinterviewhandbook.org/algorithms/hash-table/)
2. Interview · Tech Interview Handbook · [Array](https://techinterviewhandbook.org/algorithms/array/)
3. Interview · LeetCode Explore · [Hash Table card](https://leetcode.com/explore/learn/) · Needs account
4. Competitive · USACO Guide · [Introduction to Sets & Maps](https://usaco.guide/bronze/intro-sets)
5. Competitive · USACO Guide · [Hashmaps](https://usaco.guide/gold/hashmaps)
6. Competitive · USACO Guide · [Custom Comparators and Coordinate Compression](https://usaco.guide/silver/sorting-custom) · Trick

### 2. Prefix Sums
1. Interview · Hello Interview · [Prefix Sum](https://www.hellointerview.com/learn/code/prefix-sum/overview) (listed)
2. Competitive · USACO Guide · [Introduction to Prefix Sums](https://usaco.guide/silver/prefix-sums)
3. Competitive · USACO Guide · [More on Prefix Sums](https://usaco.guide/silver/more-prefix-sums)
4. Competitive · cp-algorithms · [Sparse table](https://cp-algorithms.com/data_structures/sparse-table.html) · Trick

### 3. Two Pointers
1. Interview · Hello Interview · [Two Pointers](https://www.hellointerview.com/learn/code/two-pointers/overview)
2. Competitive · USACO Guide · [Two Pointers](https://usaco.guide/silver/two-pointers)

### 4. Sliding Window
1. Interview · Hello Interview · [Sliding Window](https://www.hellointerview.com/learn/code/sliding-window/fixed-length) (listed)
2. Competitive · USACO Guide · [Sliding Window](https://usaco.guide/gold/sliding-window)
3. Competitive · cp-algorithms · [Minimum stack / Minimum queue](https://cp-algorithms.com/data_structures/stack_queue_modification.html) · Trick

### 5. Stack
1. Interview · Hello Interview · [Stack](https://www.hellointerview.com/learn/code/stack/overview) (listed)
2. Interview · Tech Interview Handbook · [Stack](https://techinterviewhandbook.org/algorithms/stack/)
3. Interview · LeetCode Explore · [Queue & Stack card](https://leetcode.com/explore/learn/) · Needs account
4. Interview · Tech Interview Handbook · [Queue](https://techinterviewhandbook.org/algorithms/queue/) · Trick
5. Competitive · cp-algorithms · [Expression parsing](https://cp-algorithms.com/string/expression_parsing.html) · Trick

### 6. Monotonic Stack and Queue
1. Interview · AlgoMonster · [Monotonic Stack](https://algo.monster/problems/mono_stack_intro)
2. Competitive · USACO Guide · [Stacks](https://usaco.guide/gold/stacks)
3. Competitive · cp-algorithms · [Minimum stack / Minimum queue](https://cp-algorithms.com/data_structures/stack_queue_modification.html)
4. Competitive · USACO Guide · [Sliding Window](https://usaco.guide/gold/sliding-window) · Trick

### 7. Linked List
1. Interview · Hello Interview · [Linked List](https://www.hellointerview.com/learn/code/linked-list/overview) (listed)
2. Interview · Tech Interview Handbook · [Linked list](https://techinterviewhandbook.org/algorithms/linked-list/)
3. Interview · LeetCode Explore · [Linked List card](https://leetcode.com/explore/learn/) · Needs account
4. Competitive · USACO Guide · [Introduction to Functional Graphs](https://usaco.guide/silver/func-graphs) (cycle finding) · Trick

### 8. Binary Search
1. Interview · Hello Interview · [Binary Search](https://www.hellointerview.com/learn/code/binary-search/overview) (listed)
2. Interview · LeetCode Explore · [Binary Search card](https://leetcode.com/explore/learn/) · Needs account
3. Competitive · USACO Guide · [Binary Search on a Sorted Array](https://usaco.guide/silver/binary-search-sorted-array)
4. Competitive · USACO Guide · [Binary Search](https://usaco.guide/silver/binary-search)
5. Competitive · cp-algorithms · [Binary search](https://cp-algorithms.com/num_methods/binary_search.html)
6. Competitive · Codeforces EDU · [ITMO Academy: Binary Search lesson](https://codeforces.com/edu/course/2) · Needs account

### 9. Sorting
1. Interview · Tech Interview Handbook · [Sorting and searching](https://techinterviewhandbook.org/algorithms/sorting-searching/)
2. Interview · VisuAlgo · [Sorting](https://visualgo.net/en/sorting)
3. Competitive · USACO Guide · [Introduction to Sorting](https://usaco.guide/bronze/intro-sorting)
4. Competitive · USACO Guide · [Custom Comparators and Coordinate Compression](https://usaco.guide/silver/sorting-custom)
5. Competitive · USACO Guide · [Sorted Sets with Custom Comparators](https://usaco.guide/gold/custom-cpp-stl) · Trick

### 10. Intervals
1. Interview · Hello Interview · [Intervals](https://www.hellointerview.com/learn/code/intervals/overview) (listed)
2. Interview · Tech Interview Handbook · [Interval](https://techinterviewhandbook.org/algorithms/interval/)
3. Competitive · USACO Guide · [Greedy Algorithms with Sorting](https://usaco.guide/silver/greedy-sorting) · Trick
4. Competitive · USACO Guide · [More on Prefix Sums](https://usaco.guide/silver/more-prefix-sums) (difference arrays) · Trick
5. Competitive · USACO Guide · [Sweep Line](https://usaco.guide/plat/sweep-line) · Trick

### 11. Heap
1. Interview · Hello Interview · [Heap](https://www.hellointerview.com/learn/code/heap/overview) (listed)
2. Interview · Tech Interview Handbook · [Heap](https://techinterviewhandbook.org/algorithms/heap/)
3. Competitive · USACO Guide · [Priority Queues](https://usaco.guide/silver/priority-queues)
4. Competitive · USACO Guide · [More Operations on Sorted Sets](https://usaco.guide/gold/intro-sorted-sets) · Trick

### 12. Tree Traversal
1. Interview · Hello Interview · [Depth-First Search](https://www.hellointerview.com/learn/code/depth-first-search/introduction) (listed)
2. Interview · Hello Interview · [Breadth-First Search](https://www.hellointerview.com/learn/code/breadth-first-search/introduction) (listed)
3. Interview · Tech Interview Handbook · [Tree](https://techinterviewhandbook.org/algorithms/tree/)
4. Interview · LeetCode Explore · [Binary Tree card](https://leetcode.com/explore/learn/) · Needs account
5. Competitive · USACO Guide · [Introduction to Tree Algorithms](https://usaco.guide/silver/intro-tree)
6. Competitive · USACO Guide · [Euler Tour Technique](https://usaco.guide/gold/tree-euler) · Trick

### 13. Binary Search Trees
1. Interview · VisuAlgo · [Binary Search Tree, AVL Tree](https://visualgo.net/en/bst)
2. Interview · Hello Interview · [Validate Binary Search Tree](https://www.hellointerview.com/learn/code/depth-first-search/validate-binary-search-tree)
3. Interview · LeetCode Explore · [Binary Search Tree card](https://leetcode.com/explore/learn/) · Needs account
4. Competitive · USACO Guide · [More Operations on Sorted Sets](https://usaco.guide/gold/intro-sorted-sets)
5. Competitive · USACO Guide · [Treaps](https://usaco.guide/adv/treaps) · Trick

### 14. Trie
1. Interview · Hello Interview · [Trie](https://www.hellointerview.com/learn/code/trie/overview) (listed)
2. Interview · Tech Interview Handbook · [Trie](https://techinterviewhandbook.org/algorithms/trie/)
3. Interview · LeetCode Explore · [Trie card](https://leetcode.com/explore/learn/) · Needs account
4. Competitive · cp-algorithms · [Aho-Corasick algorithm](https://cp-algorithms.com/string/aho_corasick.html) · Trick

### 15. Backtracking and Brute Force
1. Interview · Hello Interview · [Backtracking](https://www.hellointerview.com/learn/code/backtracking/overview) (listed)
2. Interview · Tech Interview Handbook · [Recursion](https://techinterviewhandbook.org/algorithms/recursion/)
3. Competitive · USACO Guide · [Basic Complete Search](https://usaco.guide/bronze/intro-complete)
4. Competitive · USACO Guide · [Complete Search with Recursion](https://usaco.guide/bronze/complete-rec)
5. Competitive · cp-algorithms · [Enumerating submasks](https://cp-algorithms.com/algebra/all-submasks.html) · Trick
6. Competitive · USACO Guide · [Meet In The Middle](https://usaco.guide/gold/meet-in-the-middle) · Trick

### 16. Graph Traversal
1. Interview · Tech Interview Handbook · [Graph](https://techinterviewhandbook.org/algorithms/graph/)
2. Interview · Hello Interview · [Breadth-First Search](https://www.hellointerview.com/learn/code/breadth-first-search/introduction) (listed)
3. Competitive · USACO Guide · [Graph Traversal](https://usaco.guide/silver/graph-traversal)
4. Competitive · USACO Guide · [Flood Fill](https://usaco.guide/silver/flood-fill)
5. Competitive · USACO Guide · [Introduction to Functional Graphs](https://usaco.guide/silver/func-graphs) · Trick
6. Competitive · cp-algorithms · [0-1 BFS](https://cp-algorithms.com/graph/01_bfs.html) · Trick

### 17. Topological Sort
1. Interview · Hello Interview · [Topological Sort](https://www.hellointerview.com/learn/code/graphs/topological-sort) (listed)
2. Competitive · USACO Guide · [Topological Sort](https://usaco.guide/gold/toposort)
3. Competitive · cp-algorithms · [Topological sorting](https://cp-algorithms.com/graph/topological-sort.html)
4. Competitive · cp-algorithms · [Strongly connected components](https://cp-algorithms.com/graph/strongly-connected-components.html) (condensation graph) · Trick

### 18. Union-Find
1. Interview · AlgoMonster · [Union-Find](https://algo.monster/problems/dsu_intro) · Needs account
2. Competitive · USACO Guide · [Disjoint Set Union](https://usaco.guide/gold/dsu)
3. Competitive · cp-algorithms · [Disjoint Set Union](https://cp-algorithms.com/data_structures/disjoint_set_union.html)
4. Competitive · Codeforces EDU · [ITMO Academy: Disjoint Sets Union lesson](https://codeforces.com/edu/course/2) · Needs account
5. Competitive · USACO Guide · [Minimum Spanning Trees](https://usaco.guide/gold/mst) · Trick
6. Competitive · USACO Guide · [Offline Deletion](https://usaco.guide/adv/offline-del) · Trick

### 19. Shortest Paths
1. Competitive · USACO Guide · [Shortest Paths with Unweighted Edges](https://usaco.guide/gold/unweighted-shortest-paths)
2. Competitive · USACO Guide · [Shortest Paths with Non-Negative Edge Weights](https://usaco.guide/gold/shortest-paths)
3. Competitive · cp-algorithms · [Dijkstra's algorithm](https://cp-algorithms.com/graph/dijkstra.html)
4. Competitive · cp-algorithms · [Bellman-Ford algorithm](https://cp-algorithms.com/graph/bellman_ford.html)
5. Competitive · cp-algorithms · [Floyd-Warshall algorithm](https://cp-algorithms.com/graph/all-pair-shortest-path-floyd-warshall.html)
6. Competitive · cp-algorithms · [0-1 BFS](https://cp-algorithms.com/graph/01_bfs.html) · Trick

### 20. Minimum Spanning Tree
1. Competitive · USACO Guide · [Minimum Spanning Trees](https://usaco.guide/gold/mst)
2. Competitive · cp-algorithms · [Kruskal's algorithm](https://cp-algorithms.com/graph/mst_kruskal.html)
3. Competitive · cp-algorithms · [Prim's algorithm](https://cp-algorithms.com/graph/mst_prim.html)
4. Competitive · USACO Guide · [Kruskal Reconstruction Tree](https://usaco.guide/plat/kruskal-tree) · Trick

### 21. 1-D Dynamic Programming
1. Interview · Hello Interview · [Dynamic Programming Fundamentals](https://www.hellointerview.com/learn/code/dynamic-programming/fundamentals) (listed)
2. Interview · Tech Interview Handbook · [Dynamic programming](https://techinterviewhandbook.org/algorithms/dynamic-programming/)
3. Competitive · USACO Guide · [Introduction to DP](https://usaco.guide/gold/intro-dp)
4. Competitive · USACO Guide · [Longest Increasing Subsequence](https://usaco.guide/gold/lis)
5. Competitive · cp-algorithms · [Longest increasing subsequence](https://cp-algorithms.com/dynamic_programming/longest_increasing_subsequence.html)
6. Competitive · USACO Guide · [Digit DP](https://usaco.guide/gold/digit-dp) · Trick

### 22. 2-D Dynamic Programming
1. Competitive · USACO Guide · [Paths on Grids](https://usaco.guide/gold/paths-grids)
2. Competitive · USACO Guide · [Knapsack DP](https://usaco.guide/gold/knapsack)
3. Competitive · USACO Guide · [Range DP](https://usaco.guide/gold/dp-ranges)
4. Competitive · cp-algorithms · [Knapsack problem](https://cp-algorithms.com/dynamic_programming/knapsack.html)
5. Competitive · cp-algorithms · [Divide and conquer DP](https://cp-algorithms.com/dynamic_programming/divide-and-conquer-dp.html) · Trick
6. Competitive · cp-algorithms · [Knuth's optimization](https://cp-algorithms.com/dynamic_programming/knuth-optimization.html) · Trick

### 23. Greedy
1. Interview · Hello Interview · [Greedy](https://www.hellointerview.com/learn/code/greedy/overview) (listed)
2. Competitive · USACO Guide · [Introduction to Greedy Algorithms](https://usaco.guide/bronze/intro-greedy)
3. Competitive · USACO Guide · [Greedy Algorithms with Sorting](https://usaco.guide/silver/greedy-sorting)
4. Competitive · USACO Guide · [Priority Queues](https://usaco.guide/silver/priority-queues) · Trick

### 24. Bit Manipulation
1. Interview · Tech Interview Handbook · [Binary](https://techinterviewhandbook.org/algorithms/binary/)
2. Competitive · USACO Guide · [Intro to Bitwise Operators](https://usaco.guide/silver/intro-bitwise)
3. Competitive · cp-algorithms · [Bit manipulation](https://cp-algorithms.com/algebra/bit-manipulation.html)
4. Competitive · cp-algorithms · [Enumerating submasks](https://cp-algorithms.com/algebra/all-submasks.html) · Trick
5. Competitive · USACO Guide · [XOR Basis](https://usaco.guide/adv/xor-basis) · Trick
6. Competitive · USACO Guide · [Bitsets](https://usaco.guide/plat/bitsets) · Trick

### 25. Math
1. Interview · Tech Interview Handbook · [Math](https://techinterviewhandbook.org/algorithms/math/)
2. Competitive · USACO Guide · [Divisibility](https://usaco.guide/gold/divisibility)
3. Competitive · USACO Guide · [Modular Arithmetic](https://usaco.guide/gold/modular)
4. Competitive · cp-algorithms · [Binary exponentiation](https://cp-algorithms.com/algebra/binary-exp.html) · Trick
5. Competitive · USACO Guide · [Casework](https://usaco.guide/bronze/casework) · Trick

### 26. Strings
1. Interview · Tech Interview Handbook · [String](https://techinterviewhandbook.org/algorithms/string/)
2. Competitive · cp-algorithms · [String hashing](https://cp-algorithms.com/string/string-hashing.html) · Trick
3. Competitive · cp-algorithms · [Prefix function, Knuth-Morris-Pratt](https://cp-algorithms.com/string/prefix-function.html) · Trick

### 27. Simulation and Implementation
1. Interview · Hello Interview · [Spiral Matrix](https://www.hellointerview.com/learn/code/matrices/spiral-matrix) (listed)
2. Interview · Tech Interview Handbook · [Matrix](https://techinterviewhandbook.org/algorithms/matrix/)
3. Competitive · USACO Guide · [Simulation](https://usaco.guide/bronze/simulation)
4. Competitive · USACO Guide · [Rectangle Geometry](https://usaco.guide/bronze/rect-geo) · Trick
5. Competitive · USACO Guide · [Casework](https://usaco.guide/bronze/casework) · Trick

### 28. Data Structure Design
1. Competitive · cp-algorithms · [Minimum stack / Minimum queue](https://cp-algorithms.com/data_structures/stack_queue_modification.html) · Trick

## Advanced patterns

### 29. Number Theory
1. Competitive · USACO Guide · [Divisibility](https://usaco.guide/gold/divisibility)
2. Competitive · USACO Guide · [Modular Arithmetic](https://usaco.guide/gold/modular)
3. Competitive · cp-algorithms · [Sieve of Eratosthenes](https://cp-algorithms.com/algebra/sieve-of-eratosthenes.html)
4. Competitive · cp-algorithms · [Euclidean algorithm](https://cp-algorithms.com/algebra/euclid-algorithm.html)
5. Competitive · cp-algorithms · [Extended Euclidean algorithm](https://cp-algorithms.com/algebra/extended-euclid-algorithm.html)
6. Competitive · cp-algorithms · [Modular inverse](https://cp-algorithms.com/algebra/module-inverse.html) · Trick

### 30. Chinese Remainder Theorem
1. Competitive · cp-algorithms · [Chinese remainder theorem](https://cp-algorithms.com/algebra/chinese-remainder-theorem.html)
2. Competitive · USACO Guide · [Extended Euclidean Algorithm](https://usaco.guide/adv/extend-euclid)
3. Competitive · cp-algorithms · [Modular inverse](https://cp-algorithms.com/algebra/module-inverse.html) · Trick

### 31. Combinatorics
1. Competitive · USACO Guide · [Combinatorics](https://usaco.guide/gold/combo)
2. Competitive · cp-algorithms · [Binomial coefficients](https://cp-algorithms.com/combinatorics/binomial-coefficients.html)
3. Competitive · USACO Guide · [Inclusion-Exclusion Principle](https://usaco.guide/plat/PIE)
4. Competitive · USACO Guide · [Catalan Numbers](https://usaco.guide/adv/catalan)
5. Competitive · cp-algorithms · [Modular inverse](https://cp-algorithms.com/algebra/module-inverse.html) · Trick

### 32. Probability and Expected Value
1. Competitive · Codeforces blog · [Expected value, part 1 (Errichto)](https://codeforces.com/blog/entry/62690)
2. Competitive · Codeforces blog · [Expected value, part 2 (Errichto)](https://codeforces.com/blog/entry/62792)
3. Competitive · USACO Guide · [Combinatorics](https://usaco.guide/gold/combo) · Trick

### 33. Game Theory
1. Competitive · cp-algorithms · [Sprague-Grundy theorem, Nim](https://cp-algorithms.com/game_theory/sprague-grundy-nim.html)
2. Competitive · cp-algorithms · [Games on arbitrary graphs](https://cp-algorithms.com/game_theory/games_on_graphs.html)
3. Competitive · USACO Guide · [Game Theory](https://usaco.guide/adv/game-theory)

### 34. Geometry
1. Competitive · USACO Guide · [Geometry Primitives](https://usaco.guide/plat/geo-pri)
2. Competitive · cp-algorithms · [Basic geometry](https://cp-algorithms.com/geometry/basic-geometry.html)
3. Competitive · cp-algorithms · [Convex hull](https://cp-algorithms.com/geometry/convex-hull.html)
4. Interview · Tech Interview Handbook · [Geometry](https://techinterviewhandbook.org/algorithms/geometry/)
5. Competitive · USACO Guide · [Sweep Line](https://usaco.guide/plat/sweep-line) · Trick
6. Competitive · USACO Guide · [Rectangle Geometry](https://usaco.guide/bronze/rect-geo) · Trick

### 35. Matrices and Matrix Exponentiation
1. Competitive · USACO Guide · [Matrix Exponentiation](https://usaco.guide/plat/matrix-expo)
2. Competitive · cp-algorithms · [Binary exponentiation](https://cp-algorithms.com/algebra/binary-exp.html)
3. Interview · Tech Interview Handbook · [Matrix](https://techinterviewhandbook.org/algorithms/matrix/)

### 36. FFT and NTT
1. Competitive · cp-algorithms · [Fast Fourier transform](https://cp-algorithms.com/algebra/fft.html)
2. Competitive · USACO Guide · [Introduction to Fast Fourier Transform](https://usaco.guide/adv/fft)
3. Competitive · USACO Guide · [More Complex Operations Using FFT](https://usaco.guide/adv/fft-ext)

### 37. Constructive Algorithms
1. Competitive · USACO Guide · [Ad Hoc Problems](https://usaco.guide/bronze/ad-hoc)
2. Competitive · USACO Guide · [Casework](https://usaco.guide/bronze/casework) · Trick

### 38. Divide and Conquer
1. Competitive · USACO Guide · [Divide & Conquer - SRQ](https://usaco.guide/plat/DC-SRQ)
2. Interview · AlgoMonster · [Divide and Conquer](https://algo.monster/problems/divide_and_conquer_intro)
3. Interview · VisuAlgo · [Sorting (merge sort)](https://visualgo.net/en/sorting)
4. Competitive · USACO Guide · [Divide & Conquer - DP](https://usaco.guide/plat/DC-DP) · Trick
5. Competitive · cp-algorithms · [Divide and conquer DP](https://cp-algorithms.com/dynamic_programming/divide-and-conquer-dp.html) · Trick
6. Competitive · USACO Guide · [Centroid Decomposition](https://usaco.guide/plat/centroid) · Trick

### 39. Meet in the Middle
1. Competitive · USACO Guide · [Meet In The Middle](https://usaco.guide/gold/meet-in-the-middle)

### 40. Ternary Search
1. Competitive · USACO Guide · [Optimizing Unimodal Functions](https://usaco.guide/gold/ternary-search)
2. Competitive · cp-algorithms · [Ternary search](https://cp-algorithms.com/num_methods/ternary_search.html)

### 41. Segment Tree and Fenwick Tree
1. Competitive · Codeforces EDU · [ITMO Academy: Segment Tree lessons, parts 1 and 2](https://codeforces.com/edu/course/2) · Needs account
2. Competitive · cp-algorithms · [Segment tree](https://cp-algorithms.com/data_structures/segment_tree.html)
3. Competitive · cp-algorithms · [Fenwick tree](https://cp-algorithms.com/data_structures/fenwick.html)
4. Competitive · USACO Guide · [Point Update Range Sum](https://usaco.guide/gold/PURS)
5. Competitive · USACO Guide · [Range Update Range Query](https://usaco.guide/plat/RURQ)
6. Competitive · cp-algorithms · [Sparse table](https://cp-algorithms.com/data_structures/sparse-table.html) · Trick

### 42. Tree DP
1. Competitive · USACO Guide · [DP on Trees - Introduction](https://usaco.guide/gold/dp-trees)
2. Competitive · USACO Guide · [DP on Trees - Solving For All Roots](https://usaco.guide/gold/all-roots)
3. Competitive · USACO Guide · [DP on Trees - Combining Subtrees](https://usaco.guide/adv/comb-sub)
4. Competitive · USACO Guide · [Euler Tour Technique](https://usaco.guide/gold/tree-euler) · Trick
5. Competitive · USACO Guide · [Small-To-Large Merging](https://usaco.guide/plat/merging) · Trick

### 43. Bitmask DP
1. Competitive · USACO Guide · [Bitmask DP](https://usaco.guide/gold/dp-bitmasks)
2. Competitive · cp-algorithms · [Enumerating submasks](https://cp-algorithms.com/algebra/all-submasks.html)
3. Competitive · USACO Guide · [Sum over Subsets DP](https://usaco.guide/plat/dp-sos)
4. Competitive · USACO Guide · [DP on Broken Profile](https://usaco.guide/adv/dp-broken-profile) · Trick

### 44. Lowest Common Ancestor and Tree Queries
1. Competitive · cp-algorithms · [LCA with binary lifting](https://cp-algorithms.com/graph/lca_binary_lifting.html)
2. Competitive · USACO Guide · [Binary Jumping](https://usaco.guide/plat/binary-jump)
3. Competitive · USACO Guide · [LCA with Euler Tour](https://usaco.guide/gold/lca-euler)
4. Competitive · cp-algorithms · [Heavy-light decomposition](https://cp-algorithms.com/graph/hld.html)
5. Competitive · USACO Guide · [Euler Tour Technique](https://usaco.guide/gold/tree-euler) · Trick
6. Competitive · USACO Guide · [Centroid Decomposition](https://usaco.guide/plat/centroid) · Trick

### 45. String Hashing
1. Competitive · cp-algorithms · [String hashing](https://cp-algorithms.com/string/string-hashing.html)
2. Competitive · USACO Guide · [Hashing](https://usaco.guide/gold/hashing)

### 46. String Matching
1. Competitive · cp-algorithms · [Prefix function, Knuth-Morris-Pratt](https://cp-algorithms.com/string/prefix-function.html)
2. Competitive · cp-algorithms · [Z-function](https://cp-algorithms.com/string/z-function.html)
3. Competitive · USACO Guide · [String Searching](https://usaco.guide/adv/string-search)
4. Competitive · cp-algorithms · [Aho-Corasick algorithm](https://cp-algorithms.com/string/aho_corasick.html)
5. Competitive · Codeforces EDU · [ITMO Academy: Z-function lesson](https://codeforces.com/edu/course/2) · Needs account
6. Competitive · cp-algorithms · [String hashing](https://cp-algorithms.com/string/string-hashing.html) (Rabin-Karp) · Trick

### 47. Suffix Structures
1. Competitive · cp-algorithms · [Suffix array](https://cp-algorithms.com/string/suffix-array.html)
2. Competitive · cp-algorithms · [Suffix automaton](https://cp-algorithms.com/string/suffix-automaton.html)
3. Competitive · USACO Guide · [Suffix Array](https://usaco.guide/adv/suffix-array)
4. Competitive · Codeforces EDU · [ITMO Academy: Suffix Array lesson](https://codeforces.com/edu/course/2) · Needs account
5. Competitive · USACO Guide · [String Suffix Structures](https://usaco.guide/adv/string-suffix)

### 48. Strongly Connected Components and Bridges
1. Competitive · cp-algorithms · [Strongly connected components](https://cp-algorithms.com/graph/strongly-connected-components.html)
2. Competitive · cp-algorithms · [Finding bridges](https://cp-algorithms.com/graph/bridge-searching.html)
3. Competitive · USACO Guide · [Strongly Connected Components](https://usaco.guide/adv/SCC)
4. Competitive · USACO Guide · [BCCs and 2CCs](https://usaco.guide/adv/BCC-2CC)
5. Competitive · cp-algorithms · [2-SAT](https://cp-algorithms.com/graph/2SAT.html) · Trick

### 49. Max Flow and Min Cut
1. Competitive · cp-algorithms · [Dinic's algorithm](https://cp-algorithms.com/graph/dinic.html)
2. Competitive · USACO Guide · [Maximum Flow](https://usaco.guide/adv/max-flow)
3. Competitive · USACO Guide · [Minimum Cut](https://usaco.guide/adv/min-cut)
4. Competitive · USACO Guide · [Minimum Cost Flow](https://usaco.guide/adv/min-cost-flow)
5. Competitive · USACO Guide · [Flow with Lower Bounds](https://usaco.guide/adv/flow-lb) · Trick

### 50. Bipartite Matching
1. Competitive · cp-algorithms · [Kuhn's algorithm for maximum bipartite matching](https://cp-algorithms.com/graph/kuhn_maximum_bipartite_matching.html)
2. Competitive · cp-algorithms · [Dinic's algorithm](https://cp-algorithms.com/graph/dinic.html) (matching as a flow) · Trick

### 51. 2-SAT
1. Competitive · cp-algorithms · [2-SAT](https://cp-algorithms.com/graph/2SAT.html)
2. Competitive · cp-algorithms · [Strongly connected components](https://cp-algorithms.com/graph/strongly-connected-components.html) · Trick

### 52. Interactive Problems
1. Competitive · USACO Guide · [Interactive and Communication Problems](https://usaco.guide/adv/interactive)
2. Competitive · cp-algorithms · [Binary search](https://cp-algorithms.com/num_methods/binary_search.html) · Trick

### 53. Expression Parsing
1. Competitive · cp-algorithms · [Expression parsing](https://cp-algorithms.com/string/expression_parsing.html)
2. Interview · Tech Interview Handbook · [Stack](https://techinterviewhandbook.org/algorithms/stack/) · Trick

### 54. JavaScript
1. Interview · javascript.info · [Variable scope, closure](https://javascript.info/closure)
2. Interview · javascript.info · [Promise](https://javascript.info/promise-basics)
3. Interview · javascript.info · [Prototypal inheritance](https://javascript.info/prototype-inheritance)
4. Interview · MDN Web Docs · [Closures](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Closures)

## Still missing

Data Structure Design has only a trick and no main guide, and Strings has no interview-level guide beyond the Tech Interview Handbook. Codeforces EDU and LeetCode Explore entries should link straight to their lesson or card once those addresses are checked.
