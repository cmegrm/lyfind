"""Private conversations between account holders and the CSA office."""

from users import QUICK_GUEST_EMAIL_SUFFIX, DomainError, User, require_permission


class SupportService:
    def __init__(self, db):
        self.db = db

    def overview(self, user):
        with self.db.connect() as conn:
            actor = self._actor(conn, user)
            if actor.role != 'admin':
                return self._messages(conn, actor.id)
            threads = conn.execute("""
                SELECT latest.user_id, u.name,
                       CASE WHEN u.role='guest' AND u.email LIKE ? THEN NULL ELSE u.email END AS email,
                       contact.email AS guest_contact_email,
                       substr(latest.body, 1, 180) AS last_message,
                       latest.created_at AS last_at, latest.author_role <> 'admin' AS needs_reply
                FROM support_messages AS latest
                JOIN (SELECT MAX(id) AS latest_id FROM support_messages GROUP BY user_id) AS recent
                  ON recent.latest_id = latest.id
                JOIN users AS u ON u.id = latest.user_id
                LEFT JOIN guest_visit_contacts AS contact ON contact.user_id = u.id
                ORDER BY needs_reply DESC, latest.id DESC
            """, ('%' + QUICK_GUEST_EMAIL_SUFFIX,))
            return {'threads': [dict(row, needs_reply=bool(row['needs_reply'])) for row in threads]}

    def thread(self, user, owner_id):
        with self.db.connect() as conn:
            actor = self._actor(conn, user)
            self._staff_thread(conn, actor, owner_id)
            return self._messages(conn, owner_id)

    def send(self, user, data):
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            actor = self._actor(conn, user)
            if actor.role == 'admin':
                owner_id = data.get('user_id')
                self._staff_thread(conn, actor, owner_id)
            else:
                if 'user_id' in data:
                    raise DomainError('You can only send messages in your own conversation.', 403)
                owner_id = actor.id

            body = self._message_body(data.get('message'))
            sent_recently = conn.execute("""
                SELECT COUNT(*) FROM support_messages
                WHERE sender_id=? AND created_at >= strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 minute')
            """, (actor.id,)).fetchone()[0]
            if sent_recently >= 12:
                raise DomainError('Please wait a minute before sending another message.', 429)
            conn.execute("""
                INSERT INTO support_messages(user_id,sender_id,author_role,body) VALUES(?,?,?,?)
            """, (owner_id, actor.id, actor.role, body))
            if actor.role == 'admin':
                conn.execute('INSERT INTO notifications(user_id,message) VALUES(?,?)',
                             (owner_id, 'CSA replied to your message. Open Contact CSA to read it.'))
            return self._messages(conn, owner_id)

    @staticmethod
    def _actor(conn, user):
        row = conn.execute('SELECT * FROM users WHERE id=?', (user.id if user else -1,)).fetchone()
        actor = User.from_row(row) if row else None
        require_permission(actor, 'view_own')
        return actor

    @staticmethod
    def _staff_thread(conn, actor, owner_id):
        if actor.role != 'admin':
            raise DomainError('This conversation is only available to CSA staff.', 403)
        if type(owner_id) is not int or not 1 <= owner_id <= 2**63 - 1:
            raise DomainError('Choose a conversation.')
        if conn.execute('SELECT 1 FROM support_messages WHERE user_id=? LIMIT 1', (owner_id,)).fetchone() is None:
            raise DomainError('Conversation not found.', 404)

    @staticmethod
    def _messages(conn, owner_id):
        rows = conn.execute("""
            SELECT id, body, created_at, author_role FROM support_messages WHERE user_id=? ORDER BY id
        """, (owner_id,))
        return {'messages': [dict(row) for row in rows]}

    @staticmethod
    def _message_body(value):
        body = value.strip() if isinstance(value, str) else ''
        if not body:
            raise DomainError('Enter a message.')
        if len(body) > 2000:
            raise DomainError('Use 2,000 characters or fewer.')
        if '\0' in body or any(0xD800 <= ord(char) <= 0xDFFF for char in body):
            raise DomainError('Remove the invalid characters from your message.')
        return body
