# Vigil Protocol Configuration Guide

The Expectation Agent in Vigil evaluates clinical events against hospital-defined schedules (protocols) to determine if nursing rounds, consent, or medication order documentation are on time, late, or missing. 

These rules are deterministic and driven entirely by configuration, meaning you can adjust expected schedules without changing any code.

## Where Configuration Lives
All active protocol schedules are stored in:
`backend/orchestration/expectation_agent/protocol_configs/default_protocols.yaml`

## Structure of the Configuration

The YAML file is organized by `ward_type` (e.g., ICU, General, Surgical) and contains lists of `rules`. 

### Rule Properties

| Property | Description | Example |
|---|---|---|
| `rule_id` | Unique identifier for the rule. | `icu_vitals_2h` |
| `event_type` | The type of clinical event this rule expects. | `round`, `consent`, `med_order` |
| `description` | Human-readable explanation of the rule. | `"Vitals required every 2 hours in ICU"` |
| `trigger` | When this rule applies. Currently supports `admission`, `continuous`, or specific prior events. | `continuous` |
| `frequency_hours` | How often the event must occur (for continuous triggers). | `2` |
| `grace_period_mins`| Number of minutes past the deadline before the event is considered late/missing. | `15` |
| `required_fields` | Any specific data points that must be present in the event payload for it to satisfy the rule. | `["vitals.hr", "vitals.bp"]` |

## Example `default_protocols.yaml`

```yaml
wards:
  ICU:
    rules:
      - rule_id: icu_vitals_2h
        event_type: round
        description: Vitals required every 2 hours in ICU
        trigger: continuous
        frequency_hours: 2
        grace_period_mins: 15
        required_fields:
          - vitals

  SURG:
    rules:
      - rule_id: pre_op_consent
        event_type: consent
        description: Consent required before surgical procedures
        trigger: pre_procedure
        grace_period_mins: 0

  GEN:
    rules:
      - rule_id: gen_vitals_8h
        event_type: round
        description: Vitals required every 8 hours in General ward
        trigger: continuous
        frequency_hours: 8
        grace_period_mins: 30
```

## How the Expectation Agent Uses This

The system checks the latest event of `event_type` for a patient. If the time elapsed since that event exceeds `frequency_hours` + `grace_period_mins`, a gap is created.

If a gap is found, it is sent to the Gap-Detection Agent which will classify its severity (Urgent, Routine, Documentation-Only) according to a separate, fixed rubric.
