# Fixture contract

Каждый semantic test fixture содержит:

- source WritingContract;
- realization;
- expected verdict;
- exact expected reason codes;
- optional expected alignment details.

Первые обязательные mutation cases:

1. causality upgrade;
2. qualifier drop;
3. numeric drift;
4. unit drift;
5. scope widening;
6. negation flip;
7. unauthorized new claim;
8. required claim omission;
9. evidence attribution drift;
10. precision inflation.
