import os
import discord
from discord.ext import commands
import random
import asyncio
import json
import random
import requests
import nltk
from difflib import SequenceMatcher
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import spacy
from flask import Flask, request, jsonify, render_template
import wikipediaapi

nltk.download('punkt')
nltk.download('stopwords')
nlp = spacy.load("en_core_web_sm")

BOT_TOKEN = "YOUR_TOKEN_HERE"
CHANEL_GENERAL_ID = 0 # Replace with your channel ID

wiki_wiki = wikipediaapi.Wikipedia(
    language='en',
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent="MyChatbot/1.0 (mychatbot@example.com)"  # Proper user agent
)

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
def adapt_responses(knowledge_base, user_input, feedback, new_response=None):
    for entry in knowledge_base["questions"]:
        if entry["question"] == user_input:
            found = False
            for response in entry["answers"]:
                if response["response"] == new_response:
                    if feedback.lower() == "yes":
                        response["score"] += 1
                    elif feedback.lower() == "no":
                        response["score"] -= 1
                    found = True
                    break
            if not found and new_response:
                entry["answers"].append({"response": new_response, "score": 0})
            break
    save_knowledge_base('MindDatabase.json', knowledge_base)

def preprocess_text(text):
    tokens = word_tokenize(text.lower())
    cleaned_tokens = [token for token in tokens if token not in stopwords.words('english')]
    return cleaned_tokens

def Mind_Data_base(file_path: str) -> dict:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("Database file not found. Creating a new one with the required structure.")
        return {"questions": []}
    except json.JSONDecodeError:
        print("Database file is corrupted. Starting with an empty database.")
        return {"questions": []}

def save_knowledge_base(file_path: str, data: dict):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=2)

def find_best_response(user_question: str, questions: list[str]) -> str:
    user_question = user_question.lower().strip()
    best_match = None
    highest_score = 0.0
    for question in questions:
        score = SequenceMatcher(None, user_question, question).ratio()
        if score > highest_score:
            highest_score = score
            best_match = question
    return best_match if highest_score > 0.6 else None

def get_answers(question: str, knowledge_base: dict) -> str:
    potential_responses = [q for q in knowledge_base["questions"] if q["question"] == question]
    if potential_responses:
        responses = potential_responses[0]["answers"]
        # Ensure all responses have a 'score' key, defaulting to 0 if missing
        total = sum((resp.get("score", 0) + 1) for resp in responses)  # Avoid zero or negative total
        pick = random.uniform(0, total)
        current = 0
        for response in responses:
            current += response.get("score", 0) + 1
            if current >= pick:
                return response["response"]
    return "I don't have an answer to that yet."


def analyze_input(input_text):
    doc = nlp(input_text)
    return {ent.label_: ent.text for ent in doc.ents}

@bot.command(name='chat')
async def ask_question(ctx, *, question: str = None):
    if question is None:
        await ctx.send("Please provide a question. Usage: `!chat <your question here>`")
        return
    knowledge_base = Mind_Data_base('MindDatabase.json')
    best_match = find_best_response(question, [q["question"] for q in knowledge_base["questions"]])

    if best_match:
        answer = get_answers(best_match, knowledge_base)
        await ctx.send(f"{answer}\n\nWas this response helpful? (yes/no)")
        try:
            feedback = await bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"], timeout=30.0)
            if feedback.content.lower() == "no":
                await ctx.send("Could you provide a better response?")
                new_answer = await bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60.0)
                adapt_responses(knowledge_base, best_match, "yes", new_answer.content)
                await ctx.send("New response learned. Thank you!")
            else:
                adapt_responses(knowledge_base, best_match, "yes", answer)
                await ctx.send("Thank you for your feedback!")
        except asyncio.TimeoutError:
            await ctx.send("No feedback received.")
    else:
        await ctx.send("I am not sure how to respond to that. Can you teach me the correct response?")
        try:
            new_answer = await bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60.0)
            knowledge_base['questions'].append({"question": question, "answers": [{"response": new_answer.content, "score": 0}]})
            save_knowledge_base('MindDatabase.json', knowledge_base)
            await ctx.send("Response learned. Thank you!")
        except asyncio.TimeoutError:
            await ctx.send("Timed out waiting for a response.")

def update_knowledge_base_with_scores(file_path: str):
    try:
        with open(file_path, 'r+') as file:
            data = json.load(file)
            for question in data["questions"]:
                for answer in question["answers"]:
                    if 'score' not in answer:
                        answer['score'] = 0  # Set a default score
            file.seek(0)
            json.dump(data, file, indent=2)
            file.truncate()
    except FileNotFoundError:
        print("Database file not found.")
    except json.JSONDecodeError:
        print("Database file is corrupted.")

update_knowledge_base_with_scores('MindDatabase.json')


@bot.command(name='ask')
async def fetch_wiki(ctx, *, query: str):
    page = wiki_wiki.page(query)
    if page.exists():
        # Send the first 1000 characters of the summary or less if the summary is shorter
        summary = page.summary[0:1000] + ('...' if len(page.summary) > 1000 else '')
        await ctx.send(f"**{page.title}**\n{summary}\nRead more: <{page.fullurl}>")
    else:
        await ctx.send(f"Sorry, I couldn't find a page for '{query}' on Wikipedia.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

# Replace 'your_bot_token_here' with your actual Discord bot token.
bot.run(BOT_TOKEN)
