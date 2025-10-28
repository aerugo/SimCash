# LLM-Editable Decision Tree Format (Rust-Safe)

For **LLM runtime editing**, you need a **declarative, validated format** that's safe to parse and execute. Here's my recommendation:

---

## 🏆 Recommended: JSON with Schema Validation + Interpreter

This gives you:
- ✅ LLM-friendly (GPT-4 excels at JSON manipulation)
- ✅ Strict validation before execution (reject malicious/broken trees)
- ✅ Sandboxed evaluation (no code execution)
- ✅ Full nesting and dynamic conditions
- ✅ Easy to serialize/deserialize

---

## 1. **JSON Tree Format**

```json
{
  "version": "1.0",
  "tree_id": "rtgs_decision_main",
  "root": {
    "node_id": "N1",
    "type": "condition",
    "description": "Check if deadline is critical",
    "condition": {
      "op": "or",
      "conditions": [
        {
          "op": "<=",
          "left": {"field": "ticks_to_deadline"},
          "right": {"value": 5}
        },
        {
          "op": "==",
          "left": {"field": "tx_type"},
          "right": {"value": "Critical"}
        }
      ]
    },
    "on_true": {
      "node_id": "N1_1",
      "type": "condition",
      "description": "Check if sufficient balance available",
      "condition": {
        "op": ">=",
        "left": {"field": "balance"},
        "right": {"field": "amount"}
      },
      "on_true": {
        "node_id": "A1",
        "type": "action",
        "action": "Release",
        "parameters": {
          "credit_draw": {"value": 0.0},
          "priority_override": {"value": true},
          "pace_splits": {"value": 1}
        }
      },
      "on_false": {
        "node_id": "N1_2",
        "type": "condition",
        "description": "Check if credit headroom available",
        "condition": {
          "op": ">",
          "left": {"field": "credit_headroom"},
          "right": {"value": 0}
        },
        "on_true": {
          "node_id": "A2",
          "type": "action",
          "action": "ReleaseWithCredit",
          "parameters": {
            "credit_draw": {
              "compute": {
                "op": "-",
                "left": {"field": "amount"},
                "right": {"field": "balance"}
              }
            },
            "priority_override": {"value": true}
          }
        },
        "on_false": {
          "node_id": "A3",
          "type": "action",
          "action": "EmergencyRelease",
          "parameters": {
            "credit_draw": {"field": "credit_headroom"},
            "priority_override": {"value": true}
          }
        }
      }
    },
    "on_false": {
      "node_id": "N2",
      "type": "condition",
      "description": "Check if can settle without credit",
      "condition": {
        "op": ">=",
        "left": {"field": "balance"},
        "right": {"field": "amount"}
      },
      "on_true": {
        "node_id": "N2_1",
        "type": "condition",
        "description": "Check queue age",
        "condition": {
          "op": ">",
          "left": {"field": "queue_age"},
          "right": {"param": "age_high_threshold"}
        },
        "on_true": {
          "node_id": "A1",
          "type": "action",
          "action": "Release",
          "parameters": {
            "credit_draw": {"value": 0.0}
          }
        },
        "on_false": {
          "node_id": "N3",
          "type": "action",
          "action": "Hold",
          "parameters": {}
        }
      },
      "on_false": {
        "node_id": "N4",
        "type": "action",
        "action": "Hold",
        "parameters": {}
      }
    }
  },
  "parameters": {
    "deadline_critical_threshold": 5,
    "age_high_threshold": 10,
    "large_tx_ratio": 1.5,
    "inflow_horizon": 8,
    "eod_window": 10,
    "credit_rate_per_tick": 0.0001
  }
}
```

---

## 2. **Rust Implementation (Safe Interpreter)**

```rust
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use anyhow::{Result, Context, bail};

// ============================================================================
// TREE DEFINITION (DESERIALIZED FROM JSON)
// ============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionTreeDef {
    pub version: String,
    pub tree_id: String,
    pub root: TreeNode,
    #[serde(default)]
    pub parameters: HashMap<String, f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum TreeNode {
    Condition {
        node_id: String,
        #[serde(default)]
        description: String,
        condition: Expression,
        on_true: Box<TreeNode>,
        on_false: Box<TreeNode>,
    },
    Action {
        node_id: String,
        action: ActionType,
        parameters: HashMap<String, ValueOrCompute>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "lowercase")]
pub enum Expression {
    // Comparison operators
    #[serde(rename = "==")]
    Equal { left: Value, right: Value },
    
    #[serde(rename = "!=")]
    NotEqual { left: Value, right: Value },
    
    #[serde(rename = "<")]
    LessThan { left: Value, right: Value },
    
    #[serde(rename = "<=")]
    LessOrEqual { left: Value, right: Value },
    
    #[serde(rename = ">")]
    GreaterThan { left: Value, right: Value },
    
    #[serde(rename = ">=")]
    GreaterOrEqual { left: Value, right: Value },
    
    // Logical operators
    And {
        conditions: Vec<Expression>,
    },
    
    Or {
        conditions: Vec<Expression>,
    },
    
    Not {
        condition: Box<Expression>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Value {
    Field { field: String },
    Param { param: String },
    Literal { value: serde_json::Value },
    Compute { compute: Box<Computation> },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op")]
pub enum Computation {
    #[serde(rename = "+")]
    Add { left: Value, right: Value },
    
    #[serde(rename = "-")]
    Subtract { left: Value, right: Value },
    
    #[serde(rename = "*")]
    Multiply { left: Value, right: Value },
    
    #[serde(rename = "/")]
    Divide { left: Value, right: Value },
    
    #[serde(rename = "max")]
    Max { values: Vec<Value> },
    
    #[serde(rename = "min")]
    Min { values: Vec<Value> },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ValueOrCompute {
    Direct { value: serde_json::Value },
    Field { field: String },
    Param { param: String },
    Compute { compute: Computation },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum ActionType {
    Release,
    ReleaseWithCredit,
    PaceAndRelease,
    Hold,
    EmergencyRelease,
}

// ============================================================================
// EVALUATION CONTEXT
// ============================================================================

pub struct EvalContext {
    pub fields: HashMap<String, f64>,
    pub string_fields: HashMap<String, String>,
    pub parameters: HashMap<String, f64>,
}

impl EvalContext {
    pub fn new(
        tx: &Transaction,
        bank: &BankState,
        env: &Environment,
        params: &HashMap<String, f64>,
    ) -> Self {
        let mut fields = HashMap::new();
        let mut string_fields = HashMap::new();
        
        // Transaction fields
        fields.insert("amount".to_string(), tx.amount);
        fields.insert("deadline_tick".to_string(), tx.deadline_tick as f64);
        fields.insert("arrival_tick".to_string(), tx.arrival_tick as f64);
        fields.insert("queue_age".to_string(), tx.queue_age as f64);
        fields.insert("delay_penalty_slope".to_string(), tx.delay_penalty_slope);
        string_fields.insert("tx_type".to_string(), format!("{:?}", tx.tx_type));
        
        // Bank state fields
        fields.insert("balance".to_string(), bank.balance);
        fields.insert("credit_headroom".to_string(), bank.credit_headroom);
        fields.insert("collateral_posted".to_string(), bank.collateral_posted);
        fields.insert("tick_current".to_string(), bank.tick_current as f64);
        fields.insert("tick_eod".to_string(), bank.tick_eod as f64);
        
        // Derived fields
        let ticks_to_deadline = tx.deadline_tick.saturating_sub(bank.tick_current);
        let ticks_to_eod = bank.tick_eod.saturating_sub(bank.tick_current);
        fields.insert("ticks_to_deadline".to_string(), ticks_to_deadline as f64);
        fields.insert("ticks_to_eod".to_string(), ticks_to_eod as f64);
        fields.insert("liquidity_shortfall".to_string(), (tx.amount - bank.balance).max(0.0));
        fields.insert("effective_liquidity".to_string(), bank.balance + bank.credit_headroom);
        
        // Environment fields
        fields.insert("system_throughput".to_string(), env.system_throughput);
        fields.insert("queue_pressure".to_string(), env.queue_pressure);
        
        // Expected inflows (sum over horizon)
        let inflow_sum: f64 = env.expected_inflows.values().sum();
        fields.insert("expected_inflows_total".to_string(), inflow_sum);
        
        Self {
            fields,
            string_fields,
            parameters: params.clone(),
        }
    }
}

// ============================================================================
// SAFE INTERPRETER
// ============================================================================

pub struct TreeInterpreter {
    tree: DecisionTreeDef,
    max_depth: usize,
}

impl TreeInterpreter {
    pub fn new(tree_json: &str) -> Result<Self> {
        let tree: DecisionTreeDef = serde_json::from_str(tree_json)
            .context("Failed to parse decision tree JSON")?;
        
        // Validate tree structure
        Self::validate_tree(&tree)?;
        
        Ok(Self {
            tree,
            max_depth: 100, // Prevent infinite recursion
        })
    }
    
    pub fn from_tree(tree: DecisionTreeDef) -> Result<Self> {
        Self::validate_tree(&tree)?;
        Ok(Self {
            tree,
            max_depth: 100,
        })
    }
    
    /// Validate tree before allowing execution (CRITICAL FOR SAFETY)
    fn validate_tree(tree: &DecisionTreeDef) -> Result<()> {
        // Check version
        if tree.version != "1.0" {
            bail!("Unsupported tree version: {}", tree.version);
        }
        
        // Validate all node IDs are unique
        let mut seen_ids = std::collections::HashSet::new();
        Self::validate_node_ids(&tree.root, &mut seen_ids)?;
        
        // Validate parameter references
        Self::validate_params(&tree.root, &tree.parameters)?;
        
        Ok(())
    }
    
    fn validate_node_ids(
        node: &TreeNode,
        seen: &mut std::collections::HashSet<String>,
    ) -> Result<()> {
        let id = match node {
            TreeNode::Condition { node_id, on_true, on_false, .. } => {
                Self::validate_node_ids(on_true, seen)?;
                Self::validate_node_ids(on_false, seen)?;
                node_id
            }
            TreeNode::Action { node_id, .. } => node_id,
        };
        
        if !seen.insert(id.clone()) {
            bail!("Duplicate node ID: {}", id);
        }
        
        Ok(())
    }
    
    fn validate_params(
        node: &TreeNode,
        params: &HashMap<String, f64>,
    ) -> Result<()> {
        match node {
            TreeNode::Condition { condition, on_true, on_false, .. } => {
                Self::validate_expression_params(condition, params)?;
                Self::validate_params(on_true, params)?;
                Self::validate_params(on_false, params)?;
            }
            TreeNode::Action { .. } => {
                // Could validate action parameters here
            }
        }
        Ok(())
    }
    
    fn validate_expression_params(
        expr: &Expression,
        params: &HashMap<String, f64>,
    ) -> Result<()> {
        match expr {
            Expression::Equal { left, right }
            | Expression::NotEqual { left, right }
            | Expression::LessThan { left, right }
            | Expression::LessOrEqual { left, right }
            | Expression::GreaterThan { left, right }
            | Expression::GreaterOrEqual { left, right } => {
                Self::validate_value_params(left, params)?;
                Self::validate_value_params(right, params)?;
            }
            Expression::And { conditions } | Expression::Or { conditions } => {
                for cond in conditions {
                    Self::validate_expression_params(cond, params)?;
                }
            }
            Expression::Not { condition } => {
                Self::validate_expression_params(condition, params)?;
            }
        }
        Ok(())
    }
    
    fn validate_value_params(value: &Value, params: &HashMap<String, f64>) -> Result<()> {
        if let Value::Param { param } = value {
            if !params.contains_key(param) {
                bail!("Referenced parameter not found: {}", param);
            }
        }
        Ok(())
    }
    
    /// Main evaluation entry point
    pub fn evaluate(
        &self,
        tx: &Transaction,
        bank: &BankState,
        env: &Environment,
    ) -> Result<Decision> {
        let context = EvalContext::new(tx, bank, env, &self.tree.parameters);
        self.eval_node(&self.tree.root, &context, 0)
    }
    
    fn eval_node(
        &self,
        node: &TreeNode,
        context: &EvalContext,
        depth: usize,
    ) -> Result<Decision> {
        if depth > self.max_depth {
            bail!("Max tree depth exceeded (possible cycle)");
        }
        
        match node {
            TreeNode::Condition { condition, on_true, on_false, .. } => {
                let result = self.eval_expression(condition, context)?;
                let next_node = if result { on_true } else { on_false };
                self.eval_node(next_node, context, depth + 1)
            }
            TreeNode::Action { action, parameters, .. } => {
                self.build_decision(action, parameters, context)
            }
        }
    }
    
    fn eval_expression(&self, expr: &Expression, context: &EvalContext) -> Result<bool> {
        match expr {
            Expression::Equal { left, right } => {
                let l = self.eval_value(left, context)?;
                let r = self.eval_value(right, context)?;
                Ok((l - r).abs() < 1e-9)
            }
            Expression::NotEqual { left, right } => {
                let l = self.eval_value(left, context)?;
                let r = self.eval_value(right, context)?;
                Ok((l - r).abs() >= 1e-9)
            }
            Expression::LessThan { left, right } => {
                Ok(self.eval_value(left, context)? < self.eval_value(right, context)?)
            }
            Expression::LessOrEqual { left, right } => {
                Ok(self.eval_value(left, context)? <= self.eval_value(right, context)?)
            }
            Expression::GreaterThan { left, right } => {
                Ok(self.eval_value(left, context)? > self.eval_value(right, context)?)
            }
            Expression::GreaterOrEqual { left, right } => {
                Ok(self.eval_value(left, context)? >= self.eval_value(right, context)?)
            }
            Expression::And { conditions } => {
                for cond in conditions {
                    if !self.eval_expression(cond, context)? {
                        return Ok(false);
                    }
                }
                Ok(true)
            }
            Expression::Or { conditions } => {
                for cond in conditions {
                    if self.eval_expression(cond, context)? {
                        return Ok(true);
                    }
                }
                Ok(false)
            }
            Expression::Not { condition } => {
                Ok(!self.eval_expression(condition, context)?)
            }
        }
    }
    
    fn eval_value(&self, value: &Value, context: &EvalContext) -> Result<f64> {
        match value {
            Value::Field { field } => {
                context.fields.get(field)
                    .copied()
                    .ok_or_else(|| anyhow::anyhow!("Field not found: {}", field))
            }
            Value::Param { param } => {
                context.parameters.get(param)
                    .copied()
                    .ok_or_else(|| anyhow::anyhow!("Parameter not found: {}", param))
            }
            Value::Literal { value } => {
                if let Some(num) = value.as_f64() {
                    Ok(num)
                } else if let Some(s) = value.as_str() {
                    // Handle string comparisons by lookup
                    Ok(if context.string_fields.values().any(|v| v == s) { 1.0 } else { 0.0 })
                } else {
                    bail!("Unsupported literal type")
                }
            }
            Value::Compute { compute } => {
                self.eval_computation(compute, context)
            }
        }
    }
    
    fn eval_computation(&self, comp: &Computation, context: &EvalContext) -> Result<f64> {
        match comp {
            Computation::Add { left, right } => {
                Ok(self.eval_value(left, context)? + self.eval_value(right, context)?)
            }
            Computation::Subtract { left, right } => {
                Ok(self.eval_value(left, context)? - self.eval_value(right, context)?)
            }
            Computation::Multiply { left, right } => {
                Ok(self.eval_value(left, context)? * self.eval_value(right, context)?)
            }
            Computation::Divide { left, right } => {
                let r = self.eval_value(right, context)?;
                if r.abs() < 1e-9 {
                    bail!("Division by zero");
                }
                Ok(self.eval_value(left, context)? / r)
            }
            Computation::Max { values } => {
                values.iter()
                    .map(|v| self.eval_value(v, context))
                    .collect::<Result<Vec<_>>>()?
                    .into_iter()
                    .fold(f64::NEG_INFINITY, f64::max)
                    .pipe(Ok)
            }
            Computation::Min { values } => {
                values.iter()
                    .map(|v| self.eval_value(v, context))
                    .collect::<Result<Vec<_>>>()?
                    .into_iter()
                    .fold(f64::INFINITY, f64::min)
                    .pipe(Ok)
            }
        }
    }
    
    fn build_decision(
        &self,
        action_type: &ActionType,
        parameters: &HashMap<String, ValueOrCompute>,
        context: &EvalContext,
    ) -> Result<Decision> {
        let credit_draw = self.eval_param(parameters.get("credit_draw"), context)?.unwrap_or(0.0);
        let priority_override = self.eval_param(parameters.get("priority_override"), context)?
            .map(|v| v > 0.5)
            .unwrap_or(false);
        let pace_splits = self.eval_param(parameters.get("pace_splits"), context)?
            .unwrap_or(1.0) as u32;
        
        Ok(Decision {
            action: match action_type {
                ActionType::Release => Action::Release,
                ActionType::ReleaseWithCredit => Action::ReleaseWithCredit,
                ActionType::PaceAndRelease => Action::PaceAndRelease,
                ActionType::Hold => Action::Hold,
                ActionType::EmergencyRelease => Action::ReleaseWithCredit, // Map to existing
            },
            credit_draw,
            collateral_adjust: 0.0,
            pace_splits,
            priority_override,
        })
    }
    
    fn eval_param(
        &self,
        param: Option<&ValueOrCompute>,
        context: &EvalContext,
    ) -> Result<Option<f64>> {
        match param {
            None => Ok(None),
            Some(ValueOrCompute::Direct { value }) => {
                Ok(value.as_f64())
            }
            Some(ValueOrCompute::Field { field }) => {
                Ok(context.fields.get(field).copied())
            }
            Some(ValueOrCompute::Param { param }) => {
                Ok(context.parameters.get(param).copied())
            }
            Some(ValueOrCompute::Compute { compute }) => {
                Ok(Some(self.eval_computation(compute, context)?))
            }
        }
    }
    
    /// Allow hot-reload of tree
    pub fn reload(&mut self, tree_json: &str) -> Result<()> {
        let new_tree: DecisionTreeDef = serde_json::from_str(tree_json)?;
        Self::validate_tree(&new_tree)?;
        self.tree = new_tree;
        Ok(())
    }
}

// Helper trait for functional style
trait Pipe: Sized {
    fn pipe<F, R>(self, f: F) -> R
    where
        F: FnOnce(Self) -> R,
    {
        f(self)
    }
}

impl<T> Pipe for T {}

// ============================================================================
// USAGE EXAMPLE
// ============================================================================

pub fn example_usage() -> Result<()> {
    // Load tree from JSON file
    let tree_json = std::fs::read_to_string("decision_tree.json")?;
    let mut interpreter = TreeInterpreter::new(&tree_json)?;
    
    // Create context
    let tx = Transaction {
        id: "tx1".to_string(),
        amount: 1000.0,
        origin_bank: BankId(1),
        dest_bank: BankId(2),
        arrival_tick: 50,
        deadline_tick: 70,
        delay_penalty_slope: 0.5,
        tx_type: TxType::Normal,
        queue_age: 5,
    };
    
    let bank = BankState {
        balance: 800.0,
        credit_headroom: 2000.0,
        collateral_posted: 0.0,
        tick_current: 66,
        tick_eod: 100,
    };
    
    let env = Environment {
        expected_inflows: HashMap::new(),
        expected_outflows: HashMap::new(),
        system_throughput: 0.6,
        queue_pressure: 0.3,
        incoming_from_dest: HashMap::new(),
    };
    
    // Evaluate
    let decision = interpreter.evaluate(&tx, &bank, &env)?;
    println!("Decision: {:?}", decision);
    
    // LLM modifies tree at runtime
    let modified_tree_json = get_llm_modified_tree();
    interpreter.reload(&modified_tree_json)?;
    
    // Evaluate again with new tree
    let decision2 = interpreter.evaluate(&tx, &bank, &env)?;
    println!("Decision after LLM modification: {:?}", decision2);
    
    Ok(())
}

fn get_llm_modified_tree() -> String {
    // In practice, this would be generated by your LLM
    r#"{ ... modified tree ... }"#.to_string()
}
```

---

## 3. **JSON Schema for Validation**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DecisionTree",
  "type": "object",
  "required": ["version", "tree_id", "root"],
  "properties": {
    "version": {
      "type": "string",
      "enum": ["1.0"]
    },
    "tree_id": {
      "type": "string"
    },
    "root": {
      "$ref": "#/definitions/TreeNode"
    },
    "parameters": {
      "type": "object",
      "additionalProperties": {"type": "number"}
    }
  },
  "definitions": {
    "TreeNode": {
      "oneOf": [
        {"$ref": "#/definitions/ConditionNode"},
        {"$ref": "#/definitions/ActionNode"}
      ]
    },
    "ConditionNode": {
      "type": "object",
      "required": ["type", "node_id", "condition", "on_true", "on_false"],
      "properties": {
        "type": {"const": "condition"},
        "node_id": {"type": "string"},
        "description": {"type": "string"},
        "condition": {"$ref": "#/definitions/Expression"},
        "on_true": {"$ref": "#/definitions/TreeNode"},
        "on_false": {"$ref": "#/definitions/TreeNode"}
      }
    },
    "ActionNode": {
      "type": "object",
      "required": ["type", "node_id", "action", "parameters"],
      "properties": {
        "type": {"const": "action"},
        "node_id": {"type": "string"},
        "action": {
          "enum": ["Release", "ReleaseWithCredit", "PaceAndRelease", "Hold"]
        },
        "parameters": {"type": "object"}
      }
    },
    "Expression": {
      "type": "object",
      "required": ["op"],
      "properties": {
        "op": {
          "enum": ["==", "!=", "<", "<=", ">", ">=", "and", "or", "not"]
        }
      }
    }
  }
}
```

---

## 4. **LLM Prompting Pattern**

```markdown
You are an AI assistant that modifies decision trees for an RTGS payment system.

Current tree:
```json
{ ... current tree ... }
```

Scenario change: "Banks are experiencing liquidity shortage. Prioritize waiting for inflows."

Task: Modify the decision tree to:
1. Increase the weight on checking expected_inflows before releasing
2. Add a new condition to check if expected_inflows > amount * 1.2 (was 1.0)
3. Only use credit for truly critical deadlines (ticks_to_deadline <= 3 instead of 5)

Output ONLY valid JSON matching the schema. Do NOT include explanation.
```

**LLM Response:**
```json
{
  "version": "1.0",
  "tree_id": "rtgs_decision_liquidity_constrained",
  "root": {
    "node_id": "N1",
    "type": "condition",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"value": 3}
    },
    "on_true": { ... },
    "on_false": {
      "node_id": "N_INFLOW_CHECK",
      "type": "condition",
      "description": "Prioritize waiting for inflows in liquidity shortage",
      "condition": {
        "op": ">",
        "left": {"field": "expected_inflows_total"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "amount"},
            "right": {"value": 1.2}
          }
        }
      },
      "on_true": {
        "node_id": "A_WAIT",
        "type": "action",
        "action": "Hold",
        "parameters": {}
      },
      "on_false": { ... }
    }
  },
  "parameters": {
    "deadline_critical_threshold": 3,
    "inflow_multiplier": 1.2
  }
}
```

---

## 5. **Alternative: S-Expressions (Lisp-like)**

Even cleaner for LLMs to manipulate:

```clojure
(tree
  :version "1.0"
  :id "rtgs_decision"
  
  (if (<= ticks_to_deadline 5)
    ; Critical deadline path
    (if (>= balance amount)
      (action :release :credit 0)
      (if (> credit_headroom 0)
        (action :release-with-credit :credit (- amount balance))
        (action :emergency :credit credit_headroom)))
    
    ; Non-critical path
    (if (>= balance amount)
      (if (> queue_age 10)
        (action :release :credit 0)
        (if (> expected_inflows_total amount)
          (action :hold)
          (action :release :credit 0)))
      
      (if (> expected_inflows_total (* amount 1.2))
        (action :hold)
        (if (> (- delay_cost credit_cost) 0)
          (action :release-with-credit :credit (- amount balance))
          (action :hold))))))
```

**Rust parser for S-expressions:**
```rust
// Use the `sexpr` crate
use sexpr::{Sexpr, Parser};

pub fn parse_sexpr_tree(s: &str) -> Result<TreeNode> {
    let parser = Parser::new(s);
    let expr = parser.parse()?;
    convert_sexpr_to_tree(&expr)
}
```

---

## 6. **Safety Checklist**

Before executing LLM-modified trees:

```rust
impl TreeInterpreter {
    pub fn safety_check(&self) -> Result<()> {
        // 1. Validate JSON schema
        Self::validate_tree(&self.tree)?;
        
        // 2. Check for cycles (no infinite loops)
        self.check_for_cycles()?;
        
        // 3. Check depth limit
        let max_depth = self.compute_max_depth(&self.tree.root);
        if max_depth > 100 {
            bail!("Tree too deep: {}", max_depth);
        }
        
        // 4. Validate all field references exist
        self.validate_field_references()?;
        
        // 5. Check for division by zero in computations
        self.check_safe_computations()?;
        
        // 6. Ensure all action types are recognized
        self.validate_action_types()?;
        
        Ok(())
    }
}
```

---

## 7. **Cargo.toml Dependencies**

```toml
[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
anyhow = "1.0"
thiserror = "1.0"

# For JSON schema validation
jsonschema = "0.17"

# Optional: S-expression support
# sexpr = "0.6"

# Optional: YAML support
# serde_yaml = "0.9"

[dev-dependencies]
proptest = "1.0"  # For fuzzing tree structures
```

---

## 🎯 Why This Approach Wins

| Concern | Solution |
|---------|----------|
| **Safety** | Sandboxed interpreter, no code execution |
| **Validation** | JSON schema + Rust validation before execution |
| **LLM-friendly** | GPT-4 excels at JSON manipulation |
| **Nesting** | Unlimited nesting via recursive structure |
| **Dynamic** | Hot-reload without recompilation |
| **Debugging** | Clear node IDs, descriptions for tracing |
| **Performance** | Compiled Rust interpreter is fast |
| **Versioning** | Track tree versions, rollback if needed |

---

## 8. **Production Pattern**

```rust
// Main simulation loop
pub struct RTGSSimulator {
    tree_interpreter: TreeInterpreter,
    tree_versions: Vec<DecisionTreeDef>,
}

impl RTGSSimulator {
    pub fn update_tree_from_llm(&mut self, llm_response: &str) -> Result<()> {
        // 1. Parse new tree
        let new_tree: DecisionTreeDef = serde_json::from_str(llm_response)?;
        
        // 2. Safety check
        TreeInterpreter::validate_tree(&new_tree)?;
        
        // 3. Test on historical data
        let test_results = self.test_tree_on_history(&new_tree)?;
        if test_results.avg_cost > self.current_avg_cost * 1.5 {
            bail!("New tree performs too poorly on historical data");
        }
        
        // 4. Save backup
        self.tree_versions.push(self.tree_interpreter.tree.clone());
        
        // 5. Deploy
        self.tree_interpreter = TreeInterpreter::from_tree(new_tree)?;
        
        Ok(())
    }
    
    pub fn rollback(&mut self) -> Result<()> {
        if let Some(prev_tree) = self.tree_versions.pop() {
            self.tree_interpreter = TreeInterpreter::from_tree(prev_tree)?;
            Ok(())
        } else {
            bail!("No previous version to rollback to")
        }
    }
}
```

This gives you **safe, LLM-editable decision trees** with full validation and rollback capability!