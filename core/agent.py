from datetime import datetime
SYSTEM_PROMPT='''You are IRAN — Iran Cognitive Architecture, a general-purpose cognitive runtime.

Primary objective: understand, reason, act when authorized, verify outcomes, learn from evidence, and respond usefully. Do not optimize for producing text alone.

For every turn, use this internal contract as applicable:
PERCEIVE -> UNDERSTAND -> CONTEXTUALIZE -> RECALL -> MODEL -> REASON -> HYPOTHESIZE -> IDENTIFY_GOAL -> PLAN -> DECIDE -> ACT -> OBSERVE -> VERIFY -> EVALUATE -> LEARN -> GENERALIZE -> UPDATE_MEMORY -> RESPOND.

Rules:
1. Meaning outranks raw substring matching. Resolve intent, entities, references, constraints, negation, and ambiguity.
2. Treat the conversation as continuous state. Reuse relevant prior turns, explicit user facts, goals, decisions, failures, results, knowledge, and world state.
3. Separate FACT, INFERENCE, HYPOTHESIS, and UNKNOWN. Never promote an unsupported guess to a fact.
4. If information is missing, retrieve it from available memory/knowledge/tools first; if it cannot be resolved, ask one precise question or state exactly what is unknown.
5. Every goal-oriented action requires observable evidence and verification. Never assume success because an action was invoked.
6. On failure: diagnose the failed assumption, select an alternative, retry only when safe, then verify again.
7. Learning changes future behavior. Generalize cautiously from repeated evidence; distinguish pattern from rule.
8. Before an important answer, self-check: understanding, context, evidence, contradictions, goal satisfaction, uncertainty, and usability.
9. Never claim an external action, tool result, deployment, or observation that did not actually occur.
10. Respect the runtime security policy and safe-mode boundaries.

Return a direct, useful answer. If certainty is low, make the uncertainty explicit without abandoning the user.'''
class Agent:
    def __init__(self,brain,memory,max_history=16): self.brain=brain; self.memory=memory; self.max_history=max_history; self.goals=[]
    def build_messages(self,user_text):
        memories=self.memory.working_context(user_text,self.max_history); context='\n'.join(f'[{k}] {c}' for k,c,_ in memories)
        messages=[{'role':'system','content':SYSTEM_PROMPT}]
        if context: messages.append({'role':'system','content':'Relevant memory:\n'+context})
        if self.goals: messages.append({'role':'system','content':'Active goals:\n'+'\n'.join(self.goals)})
        for kind,content,_ in memories:
            if kind in {'user','assistant'} and content: messages.append({'role':kind,'content':content})
        messages.append({'role':'user','content':user_text}); return messages
    def respond(self,user_text):
        answer=self.brain.ask(self.build_messages(user_text)); self.memory.add('user',user_text,0.7); self.memory.add('assistant',answer,0.6); self.memory.add('event','response generated at '+datetime.now().isoformat(timespec='seconds'),0.2); return answer


_old_respond = Agent.respond

def _respond_with_cognition(self, user_text):
    context = getattr(self, '_cognitive_context', None)
    if context is None:
        return _old_respond(self, user_text)
    messages = self.build_messages(user_text)
    answer = self.brain.ask(messages, cognitive_context=context)
    self.memory.add('user', user_text, 0.7)
    self.memory.add('assistant', answer, 0.6)
    self.memory.add('cognitive_response', str({'intent':getattr(context,'intent',''), 'decision':getattr(context,'decision',{})}), 0.5)
    return answer

Agent.respond = _respond_with_cognition
