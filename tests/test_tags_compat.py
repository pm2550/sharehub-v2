"""Tag helpers support existing name-only and newer slug-based schemas."""
import sqlite3
import unittest
from app.services import tags

class TagsCompatibilityTests(unittest.TestCase):
    def test_read_and_write_both_schemas(self):
        for modern in (False, True):
            with self.subTest(modern=modern):
                db = sqlite3.connect(':memory:')
                db.row_factory = sqlite3.Row
                slug_column = ', slug TEXT UNIQUE NOT NULL' if modern else ', usage_count INTEGER DEFAULT 0'
                db.execute('CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT UNIQUE, created_at TEXT' + slug_column + ')')
                db.execute('CREATE TABLE post_tags (post_id INTEGER, tag_id INTEGER, created_at TEXT, PRIMARY KEY(post_id, tag_id))')
                name = '樱花 Studio'
                tags.add_tags_to_post(db, 7, [name, name, '  '])
                rows = tags.get_post_tags(db, 7)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['name'], name)
                expected = tags.slugify(name) if modern else name
                self.assertEqual(rows[0]['slug'], expected)
                self.assertEqual(tags.get_tag_by_slug(db, expected)['id'], rows[0]['id'])
                self.assertIsNone(tags.get_tag_by_slug(db, "missing' OR 1=1 --"))
                popular = tags.get_popular_tags(db)
                self.assertEqual(popular[0]['post_count'], 1)
                self.assertEqual(popular[0]['slug'], expected)
                db.close()

if __name__ == '__main__':
    unittest.main()
