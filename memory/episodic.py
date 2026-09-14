from datetime import datetime, timedelta
import re

class EpisodicMemory:
    """Time-aware episodic retrieval over the durable Memory SQLite store."""
    def __init__(self, memory):
        self.memory = memory
        self.conn = memory.conn

    def _norm(self, text):
        return re.sub(r"\s+", " ", str(text).strip().replace("ي", "ی").replace("ك", "ک"))

    def _tokens(self, text):
        return set(re.findall(r"[\wآ-ی]+", self._norm(text).lower()))

    def _parse_time(self, query):
        q = self._norm(query)
        now = datetime.now()
        if "دیروز" in q:
            d = (now - timedelta(days=1)).date()
            return datetime.combine(d, datetime.min.time()), datetime.combine(d, datetime.max.time()), "دیروز"
        if "امروز" in q:
            d = now.date()
            return datetime.combine(d, datetime.min.time()), datetime.combine(d, datetime.max.time()), "امروز"
        if "پریروز" in q:
            d = (now - timedelta(days=2)).date()
            return datetime.combine(d, datetime.min.time()), datetime.combine(d, datetime.max.time()), "پریروز"
        if "هفته قبل" in q:
            end = now - timedelta(days=now.weekday()+1)
            start = end - timedelta(days=6)
            return datetime.combine(start.date(), datetime.min.time()), datetime.combine(end.date(), datetime.max.time()), "هفته قبل"
        return None, None, None

    def retrieve(self, query, limit=8, kind=None):
        q = self._tokens(query)
        start, end, temporal = self._parse_time(query)
        sql = "SELECT id,kind,content,importance,access_count,created_at,confidence,source FROM memories"
        args = []
        clauses = []
        if kind:
            clauses.append("kind=?"); args.append(kind)
        if start:
            clauses.append("created_at>=?"); args.append(start.isoformat(timespec="seconds"))
            clauses.append("created_at<=?"); args.append(end.isoformat(timespec="seconds"))
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT 5000"
        rows = self.conn.execute(sql, args).fetchall()
        scored = []
        for row in rows:
            ident, k, content, importance, access, created, confidence, source = row
            toks = self._tokens(content)
            overlap = len(q & toks) / max(1, len(q))
            topic = len((q - {"یادت", "هست", "درباره", "چی", "گفتیم", "بگو"}) & toks)
            phrase = float(" ".join(sorted(q)) in content.lower()) if q else 0.0
            score = .50*overlap + .18*min(1, topic/3) + .12*float(importance) + .10*float(confidence) + .10*min(1, (access or 0)/5)
            if temporal:
                score += .18
            scored.append((score, row))
        scored.sort(key=lambda x: (x[0], x[1][0]), reverse=True)
        out=[]; seen=set()
        for score,row in scored:
            key=(row[1],row[2])
            if key in seen: continue
            seen.add(key)
            out.append({"id":row[0],"kind":row[1],"content":row[2],"created_at":row[5],"confidence":row[6],"source":row[7],"score":round(score,3)})
            if len(out)>=int(limit): break
        return out

    def summarize(self, query, limit=8):
        rows=self.retrieve(query,limit)
        return {"query":self._norm(query),"temporal":self._parse_time(query)[2],"count":len(rows),"episodes":rows}
