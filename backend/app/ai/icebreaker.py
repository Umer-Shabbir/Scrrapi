from anthropic import AsyncAnthropic


class IcebreakerGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = AsyncAnthropic(api_key=self.api_key)

    async def generate_icebreaker(
        self,
        name: str | None,
        category: str | None,
        pain_points: list[str] | None,
        positive_highlights: list[str] | None,
        review_sentiment: str | None,
    ) -> str | None:
        if not self.api_key:
            return None

        # Assemble the data
        business_name = name or "the business"
        biz_category = category or "business"
        pains = ", ".join(pain_points) if pain_points else "none noted"
        highlights = ", ".join(positive_highlights) if positive_highlights else "none noted"
        sentiment = review_sentiment or "unknown"

        prompt = (
            'You are an expert sales development representative writing a personalized '
            '"icebreaker" for a cold email. Your goal is to write a single, catchy, '
            'highly-personalized paragraph (2-3 sentences max) to open a sales email '
            f'to {business_name}.\n\n'
            'Business context available:\n'
            f'- Category: {biz_category}\n'
            f'- General Review Sentiment: {sentiment}\n'
            f'- Customer Pain Points (friction mentioned by reviewers): {pains}\n'
            f'- Customer Highlights (things reviewers love): {highlights}\n\n'
            'Instructions:\n'
            '1. If there are pain points, use a sympathetic, value-add tone '
            '("I noticed a few recent reviews mentioned...").\n'
            '2. If there are mostly positive highlights, use a congratulatory tone '
            '("Love to see the praise you\'re getting for...").\n'
            '3. DO NOT pitch a specific product or sell anything directly. Just open the '
            'conversation.\n'
            '4. Keep it very conversational, natural, and under 50 words.\n'
            '5. Return ONLY the icebreaker text. No generic greetings, no sign-offs, '
            'no quotes, no extra output.'
        )

        try:
            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception:
            return None
