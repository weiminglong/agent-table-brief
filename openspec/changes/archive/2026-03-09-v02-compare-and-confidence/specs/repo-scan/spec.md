## MODIFIED Requirements

### Requirement: Alternative Suggestions
The system SHALL surface likely alternate tables when strong similarities exist.

#### Scenario: neighboring models
- **WHEN** two models have similar names or shared upstreams
- **THEN** the brief may include them in `alternatives`

#### Scenario: grain-match bonus
- **WHEN** two models share the same inferred grain
- **THEN** the alternatives scoring awards a grain-match bonus, increasing the likelihood they appear as alternatives

#### Scenario: filter-divergence signal
- **WHEN** two models share a name prefix but have different filter sets
- **THEN** the alternatives scoring awards a filter-divergence bonus, surfacing the pair as alternatives since they are the most confusing to distinguish
