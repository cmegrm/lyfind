"""Use the proposal scoring model through the modular workflow interface."""
from lyfind.gemini_matching import GeminiMatchingService
from matching import MatchingServiceFactory, AIMatchingService


class ProposalMatcher:
    def __init__(self, ai, typed_only=False):
        adapter = None if typed_only else ai.adapter
        adapter_method = getattr(adapter, 'matching_method', '')
        if adapter is not None and adapter_method == 'gemini_ai':
            self.engine = GeminiMatchingService(adapter, weights=ai.weights)
            self.method = 'gemini_ai'
            self.model_id = getattr(adapter, 'model', 'gemini')
        else:
            clip = None if typed_only else getattr(adapter, '_clip', adapter)
            photo = getattr(adapter, '_instance', None)
            if adapter_method == 'dino_ai':
                clip, photo = None, adapter
            self.engine = MatchingServiceFactory.create(clip is not None, clip, weights=ai.weights, photo_adapter=photo)
            self.method = adapter_method if (clip is not None and adapter_method) else self.engine.method
            self.model_id = ai.status().get('model', '') or self.method

    def evaluate(self, report, item):
        if isinstance(self.engine, (AIMatchingService, GeminiMatchingService)):
            score, level, details = self.engine.evaluate(report, item)
        else:
            score, level = self.engine.compare(report, item)
            details = self.engine.explain(report, item)
        details.update(total=score, level=level, method=self.method)
        labels = dict(description='Description', photo='Photo', color='Color', brand='Brand', place='Place', date='Date')
        details['reasons'] = [
            dict(key=key, label=labels.get(key, key.title()), max=details.get('weights', {}).get(key, 0),
                 points=value or 0, state='unknown' if value is None else 'agree' if value else 'different', text='')
            for key,value in details.get('contributions', {}).items()
        ]
        details['note'] = details.get('statement', '')
        if details.get('strong_caveat'):
            details['caps'] = [details['strong_caveat']]
        return details
