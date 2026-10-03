"""Regression coverage for class-owned UserModel fact semantics."""
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from core.user_model import UserModel


def make_model():
    conn=sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE semantic_facts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "subject TEXT,predicate TEXT,value TEXT,confidence REAL,"
        "source TEXT,updated_at TEXT)"
    )
    memory=SimpleNamespace(conn=conn)
    return UserModel(memory,None),conn


def test_user_model_methods_are_class_owned_without_module_tail_rebinding():
    source=Path("core/user_model.py").read_text(encoding="utf-8")
    forbidden=(
        "UserModel.extract_explicit_facts =",
        "UserModel.facts =",
        "UserModel.answer_owned_name =",
        "UserModel.owned_name_entity_from_query =",
        "_UserModel_extract_base",
        "_UserModel_facts_base",
        "_UserModel_extract_owned_base",
    )
    assert not any(item in source for item in forbidden)

    assert UserModel.extract_explicit_facts.__qualname__=="UserModel.extract_explicit_facts"
    assert UserModel.facts.__qualname__=="UserModel.facts"
    assert UserModel.answer_owned_name.__qualname__=="UserModel.answer_owned_name"
    assert UserModel.owned_name_entity_from_query.__qualname__==(
        "UserModel.owned_name_entity_from_query"
    )


def test_owned_name_extraction_and_memory_directive_are_class_owned():
    model,_=make_model()
    facts=model.extract_explicit_facts("اسم پروژه من داناست، یادت بماند.")
    assert any(
        fact["predicate"]=="owned_name:پروژه" and fact["object"]=="دانا"
        for fact in facts
    )
    # A question must not be learned as a fact.
    asked=model.extract_explicit_facts("اسم پروژه من چیه؟")
    assert not any(
        fact["predicate"].startswith("owned_name:")
        for fact in asked
    )


def test_facts_canonicalize_and_deduplicate_at_read_time():
    model,conn=make_model()
    rows=[
        ("user","likes","قهوه را",.9,"explicit","2026-10-03T10:00:00"),
        ("user","likes","قهوه",.8,"explicit","2026-10-03T09:00:00"),
        ("user","name","سیاوش",.98,"explicit","2026-10-03T08:00:00"),
    ]
    conn.executemany(
        "INSERT INTO semantic_facts "
        "(subject,predicate,value,confidence,source,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()

    likes=model.facts(predicate="likes",limit=20)
    assert [row["object"] for row in likes]==["قهوه"]
    assert model.facts(limit=0)==[]


def test_owned_name_query_and_answer_use_same_class_owned_representation():
    model,conn=make_model()
    conn.execute(
        "INSERT INTO semantic_facts "
        "(subject,predicate,value,confidence,source,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        ("user","owned_name:شرکت","آریا",.99,"explicit","2026-10-03T10:00:00"),
    )
    conn.commit()

    assert UserModel.owned_name_entity_from_query("اسم شرکتم چی بود؟")=="شرکت"
    assert model.answer_owned_name("اسم شرکتم چی بود؟")=="اسم شرکت شما «آریا» است."
