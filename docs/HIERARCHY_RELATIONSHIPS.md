# Structural relationships as editable dyads

Open Data must not force categorical/location fields into one linear hierarchy.
The canonical structural model is a set of directed **child -> parent dyads**.
Derived paths are a UI/navigation convenience only.

Examples that must be representable simultaneously:

- `city -> state` is perfect;
- `zip -> state` is perfect;
- `zip` and `city` are not thereby nested beneath one another;
- `precinct -> city` and `precinct -> county` may both be perfect;
- `city -> county` and `county -> city` may both be imperfect/overlapping.

Each dyad records:

- child field;
- parent field;
- relationship: `perfect`, `imperfect`, `none`, or `unknown`;
- whether the value was inferred or explicitly reviewed by the user;
- bounded-sample evidence and confidence;
- any identity qualification implied by a user override;
- conflict/warning information.

## Perfect does not mean globally unique label

A perfect child-parent relationship says that each *true child identity* belongs
to one parent. It does not require the displayed child label to be globally
unique. If a sample contains `Washington County -> Oregon` and `Washington
County -> Utah`, the importer should flag the apparent conflict rather than
silently treating the source as corrupt.

If the user explicitly marks `county -> state` as perfect, Open Data treats that
as evidence that the child identity is parent-qualified, e.g.
`(county_name, state)`, while retaining a warning for review. A later stage can
use stronger identifier evidence to distinguish harmless repeated labels from a
genuine stable-ID contradiction.

## Inference rule

Every extraction test case is evidence for a general relationship class. Pairwise
functional-dependency analysis is provider-independent: for each candidate
child field, observe how many distinct parent values occur for each child value.
No observed violations supports a bounded-sample `perfect` inference; observed
multi-parent children support `imperfect`. `none` is primarily a user-reviewed
statement rather than something inferred from mere lack of functional
dependency.

## UI direction

Initial onboarding remains automatic and short. In **Configure**, users should
be able to edit only the dyads Open Data inferred, add a missing dyad, or mark an
inferred relation `none`. The UI should explain perfect versus imperfect in
plain language and surface conflicts without blocking the import.

Legacy `hierarchy_sets` / hierarchy paths should be migrated into adjacent
perfect dyads so existing configurations remain valid while the pairwise model
becomes canonical.
