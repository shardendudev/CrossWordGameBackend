import logging 
from typing import List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class MovieEmbeddingEngine:
    def __init__(self, modelName:str = settings.EMBEDDING_MODEL_NAME):
        self.modelName = modelName
        self._model = None


    def _getModel(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer 
                logger.info("Loading embedding model: %s", self.modelName)
                self._model = SentenceTransformer(self.modelName)

            except Exception as e:
                logger.warning("Could not load SentenceTransformer (%s). Fallback to zero vector.", e)
                self._model = False
            
        return self._model

    def generateMovieVector(self, movieData: Dict[str,Any]) -> List[float]:
        semanticPayload = (
            f"Title: {movieData.get('title','')}. "
            f"Genres: {movieData.get('genres','')}. "
            f"Characters: {movieData.get('character_hints','')}. "
            f"Themes: {movieData.get('theme_hints','')}. "
            f"Plot: {movieData.get('plot_hints','')}. "
            f"Trivia: {movieData.get('trivia_hints','')}. "
            f"Famous Props and MacGuffins: {movieData.get('famous_props_macguffins','')}. "
            f"Cultural Impact and Legacy: {movieData.get('cultural_impact_legacy','')}."
            )

        try:
            model = self._getModel()

            if model:
                embeddings = model.encode(semanticPayload, normalize_embeddings=True)
                return embeddings.tolist()
            return [0.0] * 1024
        except Exception as e:
            logger.warning("Could not generate the embeddings (%s)", e)
            return [0.0] * 1024
            

        


