from truebrief.ledger.database import get_supabase
from uuid import uuid4
from truebrief.api.routes import create_topic, TopicCreate, list_topics

db = get_supabase()

# 1. Create two test users
u1 = str(uuid4())
u2 = str(uuid4())
db.table('users').insert([{'id': u1, 'email': 'test1@example.com'}, {'id': u2, 'email': 'test2@example.com'}]).execute()
print(f'Created users {u1} and {u2}')

# 2. Simulate endpoint logic: user 1 creates 'AI Agents'
t1 = create_topic(TopicCreate(raw_query='AI Agents', user_id=u1))
t1_id = t1['id'] if isinstance(t1, dict) else t1.id  # TopicResponse or dict
print(f'User 1 created topic: {t1_id}')

# 3. Simulate endpoint logic: user 2 creates 'ai agents'
t2 = create_topic(TopicCreate(raw_query='ai agents', user_id=u2))
t2_id = t2['id'] if isinstance(t2, dict) else t2.id
print(f'User 2 created topic: {t2_id}')

print('Same topic ID?', t1_id == t2_id)

# 4. List topics for user 1 and user 2
l1 = list_topics(user_id=u1)
l2 = list_topics(user_id=u2)
print('User 1 topics:', len(l1))
print('User 2 topics:', len(l2))

# Cleanup
db.table('topics').delete().eq('id', t1_id).execute()
db.table('users').delete().in_('id', [u1, u2]).execute()
print('Cleaned up')
