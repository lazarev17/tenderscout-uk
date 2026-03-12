PRD: UK Tender Monitoring System
1. Обзор продукта

Название: TenderScout UK

Описание:
TenderScout — это система мониторинга государственных тендеров Великобритании, которая автоматически собирает новые закупки из официальных источников, фильтрует их по IT и Healthcare и отправляет релевантные уведомления пользователю через Telegram и email.

Цель продукта:
Сократить время поиска тендеров и не пропускать новые возможности для софтверных и health-tech компаний.

2. Проблема

Компании, работающие с госзаказами в UK, сталкиваются с проблемами:

тендеры разбросаны по разным платформам

поиск вручную занимает много времени

сложно отслеживать новые публикации

релевантные тендеры легко пропустить

3. Целевая аудитория
Основные пользователи

Software development companies

Health-tech компании

IT-консалтинг

GovTech стартапы

Вторичные пользователи

тендерные консультанты

BD менеджеры

procurement аналитики

4. Основные источники данных

Система должна агрегировать тендеры из:

Find a Tender Service

Contracts Finder

NHS England procurement notices

Tenders Electronic Daily

5. Основные функции
5.1 Сбор тендеров (Crawler)

Система должна:

регулярно запрашивать данные через API

скачивать новые тендеры

обновлять уже существующие

Частота:

каждые 30–60 минут

Поддерживаемые данные:

название тендера

описание

заказчик

бюджет

дедлайн

ссылка

дата публикации

5.2 Фильтрация тендеров

Фильтр должен находить тендеры, связанные с:

Software / IT

Ключевые слова:

software development

digital platform

IT services

SaaS

cloud services

data platform

AI / ML

Healthcare

Ключевые слова:

healthcare

NHS

patient system

electronic health record

medical software

telemedicine

5.3 Система оценки релевантности

Каждому тендеру присваивается релевантность (score).

Пример:

фактор	баллы
software keywords	+3
healthcare keywords	+3
NHS buyer	+4
budget > £100k	+2

Если score > threshold → отправляется уведомление.

6. Уведомления
6.1 Telegram

Через бота.

Сообщение:

New Tender Found

Title: Digital Healthcare Platform
Buyer: NHS Digital
Budget: £2.3M
Deadline: 14 May 2026

Link: https://...

Используется:

Telegram Bot API

6.2 Email

Пользователь получает email с:

кратким описанием

ссылкой

дедлайном

7. Хранение данных

База данных должна хранить:

Таблица tenders
поле	описание
id	уникальный id
title	название
description	описание
buyer	заказчик
budget	бюджет
deadline	срок
source	источник
published_at	дата публикации
relevance_score	score
8. Архитектура системы
Data Sources
     │
     ▼
Crawler Service
(API / scraping)
     │
     ▼
Data Processor
(cleaning + parsing)
     │
     ▼
Filter Engine
(keyword + scoring)
     │
     ▼
Database
(PostgreSQL)
     │
     ▼
Notification Service
(Email + Telegram)
9. Технологический стек
Backend

Python

FastAPI

Requests / httpx

Data

PostgreSQL

Redis (cache)

Scheduler

cron
или

Celery / worker

Infrastructure

Docker

VPS / cloud

10. Нефункциональные требования
требование	значение
latency	< 5 минут после публикации
uptime	99%
масштабируемость	до 100k тендеров
11. MVP scope

Минимальная версия должна включать:

✔ интеграция с Find a Tender API
✔ фильтрация по ключевым словам
✔ Telegram уведомления
✔ база данных
✔ cron scheduler

MVP можно сделать за 1–2 недели разработки.

12. Future features
AI анализ тендеров

LLM будет:

читать документацию

делать summary

определять сложность

Semantic search

Через embeddings:

"AI diagnostic platform"
≈
"machine learning healthcare software"
Web dashboard

Функции:

поиск тендеров

фильтры

аналитика

13. Метрики успеха

Основные KPI:

количество найденных тендеров

релевантность результатов

open rate уведомлений

количество пропущенных тендеров

✅ Ожидаемый результат:

Пользователь получает 3-10 релевантных тендеров в неделю вместо ручного поиска.