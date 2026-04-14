"""Tests for the ingest pipeline — LinkedIn parsers, career, writing."""

from echo.ingest.linkedin import parse_messages, parse_endorsements, parse_connections
from echo.ingest.career import parse_career
from echo.ingest.writing import process_writing


SAMPLE_MESSAGES_CSV = """CONVERSATION ID,CONVERSATION TITLE,FROM,SENDER PROFILE URL,TO,RECIPIENT PROFILE URLS,DATE,SUBJECT,CONTENT,FOLDER,ATTACHMENTS,IS MESSAGE DRAFT
conv1,Test,CJ Ellison,url1,Other Person,url2,2024-01-15,,Hey man sounds good for sure,INBOX,,FALSE
conv1,Test,Other Person,url2,CJ Ellison,url1,2024-01-15,,Great thanks,INBOX,,FALSE
conv2,Test,CJ Ellison,url1,Another Person,url3,2024-01-16,,Yeah definitely let me know. Thanks,INBOX,,FALSE
conv3,Test,CJ Ellison,url1,Someone,url4,2024-01-17,,What time works for you?,INBOX,,FALSE
conv4,Test,CJ Ellison,url1,Colleague,url5,2024-01-18,,Sounds good haha,INBOX,,FALSE
"""

SAMPLE_ENDORSEMENTS_CSV = """Endorsement Date,Skill Name,Endorser First Name,Endorser Last Name,Endorser Public Url,Endorsement Status
2024-01-01,Piping,John,Doe,url1,ACCEPTED
2024-01-02,Piping,Jane,Smith,url2,ACCEPTED
2024-01-03,Gas,John,Doe,url1,ACCEPTED
2024-01-04,Pipelines,Bob,Jones,url3,ACCEPTED
"""

SAMPLE_CONNECTIONS_CSV = """First Name,Last Name,URL,Email Address,Company,Position,Connected On
John,Doe,url1,john@test.com,Cenovus,Engineer,15 Jan 2024
Jane,Smith,url2,jane@test.com,FLINT,PM,20 Feb 2024
Bob,Jones,url3,bob@test.com,Cenovus,Operator,10 Mar 2023
"""


def test_parse_messages():
    stats = parse_messages(SAMPLE_MESSAGES_CSV, "CJ Ellison")
    assert stats.total_messages == 5
    assert stats.user_messages == 4
    assert stats.question_rate > 0
    assert "hey" in stats.openers or "yeah" in stats.openers or "sounds good" in stats.openers


def test_parse_messages_empty():
    stats = parse_messages(SAMPLE_MESSAGES_CSV, "Nonexistent User")
    assert stats.user_messages == 0


def test_parse_endorsements():
    stats = parse_endorsements(SAMPLE_ENDORSEMENTS_CSV)
    assert stats.total_endorsements == 4
    assert stats.unique_endorsers == 3
    assert "Piping" in stats.skills
    assert stats.skills["Piping"] == 2


def test_parse_connections():
    stats = parse_connections(SAMPLE_CONNECTIONS_CSV)
    assert stats.total_connections == 3
    assert "Cenovus" in stats.companies
    assert stats.companies["Cenovus"] == 2


def test_parse_career():
    data = {
        "positions": [
            {"title": "Pipefitter", "company": "Co A", "start_year": 2005, "end_year": 2010, "industry": "Oil & Gas"},
            {"title": "Superintendent", "company": "Co B", "start_year": 2010, "end_year": 2020, "industry": "Oil & Gas"},
            {"title": "SVP", "company": "Co C", "start_year": 2020, "industry": "Construction"},
        ]
    }
    history = parse_career(data)
    assert len(history.positions) == 3
    assert history.trajectory == ["Pipefitter", "Superintendent", "SVP"]
    assert history.total_years >= 20
    assert "Oil & Gas" in history.industries


def test_process_writing():
    sample = process_writing("This is a test. It has two sentences. Maybe three.")
    assert sample.word_count == 10
    assert sample.avg_sentence_length > 0
    assert sample.vocabulary_richness > 0
