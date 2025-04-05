from sentence_transformers import CrossEncoder


class PaddedCrossEncoder(CrossEncoder):
    def smart_batching_collate_text_only(self, batch):
        texts = [[] for _ in range(len(batch[0]))]

        for example in batch:
            for idx, text in enumerate(example):
                texts[idx].append(text.strip())

        tokenized = self.tokenizer(*texts, padding="max_length", truncation='longest_first', return_tensors="pt",
                                   max_length=self.max_length)

        for name in tokenized:
            tokenized[name] = tokenized[name].to(self._target_device)

        return tokenized