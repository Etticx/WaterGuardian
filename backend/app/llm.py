import json
import re
import httpx
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from .config import Settings, settings


class GroundedText(BaseModel):
    @model_validator(mode='after')
    def reject_unverified_units(self):
        # Calibration metadata has not been established for this integration.
        text = json.dumps(self.model_dump(), ensure_ascii=False)
        if re.search(r'\b(?:bar|bars|psi|kpa|mpa|litres?|liters?|gallons?|cubic\s+metres?|cubic\s+meters?)\b|m[³3]\s*/|\bL\s*/\s*(?:s|min|h)\b', text, flags=re.I):
            raise ValueError('Measurement units are unverified; use original sensor units.')
        return self


class Diagnosis(GroundedText):
    classification: Literal['normal', 'leak', 'sensor_fault', 'review']
    priority: Literal['low', 'medium', 'high']
    summary: str = Field(min_length=10, max_length=1200)
    evidence: list[str] = Field(min_length=1, max_length=6)
    recommended_action: str = Field(min_length=10, max_length=800)


class Plan(GroundedText):
    title: str = Field(min_length=5, max_length=160)
    instructions: str = Field(min_length=10, max_length=1600)
    crew_id: str | None


class LLMRouter:
    def __init__(self, config: Settings = settings):
        self.config = config

    def structured(self, task, payload, schema, fallback):
        cfg = self.config
        system = ('You are a water-system operations assistant. Input measurements are recorded laboratory data. '
                  'Only use supplied observations. Never invent units, leakage volume, repair completion, or field validation. '
                  'No trained Monitor means classification must be review. A model score is not a calibrated probability. '
                  'Unit metadata is absent: describe values only as original sensor units, never bar, psi, litres, or cubic metres. '
                  'Zero pump or VFD readings may mean the equipment is off; do not treat zero alone as a fault. '
                  'Without a Monitor prediction, keep the cause unconfirmed and recommend a verification inspection. '
                  'Do not identify leaks from recording names or zone names. Return a JSON object matching this schema: '
                  + json.dumps(schema.model_json_schema()))
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': task + '\n' + json.dumps(payload)}]
        errors = []
        for provider in ['groq', 'gemini', 'ollama']:
            if provider == 'groq' and not cfg.groq_api_key:
                continue
            if provider == 'gemini' and not cfg.gemini_api_key:
                continue
            try:
                with httpx.Client(timeout=cfg.llm_timeout_seconds) as client:
                    if provider == 'groq':
                        r = client.post('https://api.groq.com/openai/v1/chat/completions', headers={'Authorization': f'Bearer {cfg.groq_api_key}'}, json={
                            'model': cfg.groq_model, 'messages': messages, 'temperature': 0.1,
                            'max_completion_tokens': 1400, 'response_format': {'type': 'json_object'}})
                        r.raise_for_status()
                        content = r.json()['choices'][0]['message']['content']
                    elif provider == 'gemini':
                        r = client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{cfg.gemini_model}:generateContent',
                            headers={'x-goog-api-key': cfg.gemini_api_key}, json={
                            'systemInstruction': {'parts': [{'text': system}]},
                            'contents': [{'role': 'user', 'parts': [{'text': messages[1]['content']}]}],
                            'generationConfig': {'temperature': 0.1, 'responseMimeType': 'application/json', 'maxOutputTokens': 1800}})
                        r.raise_for_status()
                        content = ''.join(p.get('text', '') for p in r.json()['candidates'][0]['content']['parts'] if not p.get('thought'))
                    else:
                        # A missing local server fails quickly; a running model gets the full inference timeout.
                        r = client.post(cfg.ollama_base_url.rstrip('/') + '/api/chat', timeout=httpx.Timeout(cfg.llm_timeout_seconds, connect=2),
                            json={'model': cfg.ollama_model, 'messages': messages, 'stream': False, 'think': False,
                                  'format': schema.model_json_schema(), 'options': {'temperature': 0.1, 'num_predict': 1200}})
                        r.raise_for_status()
                        content = r.json()['message']['content']
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.S).strip()
                if content.startswith('```'):
                    content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content)
                result = schema.model_validate_json(content)
                return result.model_dump(), provider, errors
            except Exception as e:
                # Never log API URLs, request headers, response bodies, or credentials.
                errors.append(f'{provider}: {type(e).__name__}')
        return schema.model_validate(fallback).model_dump(), 'evidence_only', errors


router = LLMRouter()

