@agent @bdd @guardrail
Feature: Agent BDD workflow
  Agents use repository specs before changing business behavior.

  Scenario: Business behavior change starts from a behavior spec
    Given a task changes a workflow, report, AI output, compliance wording, or domain judgement
    When an agent prepares the implementation
    Then the agent checks specs for an existing matching behavior
    And the agent adds or updates a minimal Gherkin scenario before implementation when no matching behavior exists
    And verify spec parses all feature files with gherkin-v39
