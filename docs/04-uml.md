# UML: взаимодействие с CRM

## Use Case

![UML Use Case](diagrams/use-case.svg)

[Исходник PlantUML](diagrams/use-case.puml)

Основные акторы — клиент, менеджер продаж и руководитель. Автоматическое создание задач включено в сценарии регистрации и продвижения заявки. SVG показывает ключевые связи; исходник PlantUML содержит расширенный перечень действий.

## Sequence Diagram: заявка → задача → квалификация

```mermaid
sequenceDiagram
    autonumber
    actor Sales as Менеджер
    participant UI as Веб-интерфейс
    participant API as Flask API
    participant Rules as Правила воронки
    participant DB as SQLite
    Sales->>UI: Добавить клиента
    UI->>API: POST /api/leads
    API->>DB: Сохранить карточку
    API->>Rules: apply_workflow(new lead)
    Rules->>DB: Создать задачу первого контакта (+15 мин)
    API-->>UI: 201, карточка
    Sales->>UI: Завершить задачу контакта
    UI->>API: PATCH /api/tasks/{id}
    API->>DB: Закрыть задачу, статус «В работе»
    Sales->>UI: Квалифицировать заявку
    UI->>API: PUT /api/leads/{id}
    API->>Rules: apply_workflow(status changed)
    Rules->>DB: Создать задачу КП (+2 дня)
    API-->>UI: Обновлённая карточка
```

[Исходник PlantUML](diagrams/sequence.puml)

## Трассировка

| UML-сценарий | API / функция прототипа | Требование |
|---|---|---|
| Создать карточку | `POST /api/leads` | FR-01 |
| Назначить ответственного | `PUT /api/leads/{id}` | FR-03 |
| Автоматическая задача контакта | `apply_workflow()` | FR-05 |
| Завершить задачу | `PATCH /api/tasks/{id}` | FR-06 |
| Квалифицировать | `PUT /api/leads/{id}` | FR-07 |
| Посмотреть показатели | `GET /api/overview` | FR-11 |
