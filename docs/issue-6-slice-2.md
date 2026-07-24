# Issue 6 — historical dependency inference

This slice adds conservative, provider-independent functional-dependency inference over bounded historical samples.

The analyzer reports parent-to-child relationships only when:

- at least two parent values are observed;
- the child has more than one observed value;
- the configured confidence threshold is met;
- missing values are ignored rather than treated as a category.

This supports later nested entity review without changing current entity creation automatically. Observation-row identifiers remain excluded by the existing identity guard, and constant administrative fields do not create false hierarchy edges.
