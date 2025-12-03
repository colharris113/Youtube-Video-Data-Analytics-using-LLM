"""
Content Analyzer for YouTube Video Data Analytics

Performs NLP analysis on video titles and descriptions to:
1. Extract topics and keywords
2. Cluster similar content
3. Analyze performance by content cluster
4. Provide content strategy insights
"""

import pandas as pd
import numpy as np
import re
from typing import List, Dict, Tuple, Optional, Any
import logging

# Try to import NLP libraries (optional dependencies)
NLTK_AVAILABLE = False
SKLEARN_AVAILABLE = False

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    from nltk.stem import WordNetLemmatizer
    NLTK_AVAILABLE = True
except ImportError:
    print("[INFO] nltk not installed. Install with: pip install nltk")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    SKLEARN_AVAILABLE = True
except ImportError:
    print("[INFO] scikit-learn not installed. Install with: pip install scikit-learn")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Analyzes YouTube video content for topics and patterns."""

    def __init__(self):
        """Initialize the content analyzer."""
        self.vectorizer = None
        self.cluster_model = None
        self.stop_words = None
        self.lemmatizer = None
        self.nltk_available = NLTK_AVAILABLE
        self.sklearn_available = SKLEARN_AVAILABLE

        # Initialize NLP tools if available
        if self.nltk_available:
            try:
                # Download required NLTK data
                nltk.download('punkt', quiet=True)
                nltk.download('stopwords', quiet=True)
                nltk.download('wordnet', quiet=True)

                self.stop_words = set(stopwords.words('english'))
                self.lemmatizer = WordNetLemmatizer()
                logger.info("NLTK tools initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize NLTK: {e}")
                self.nltk_available = False

    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for analysis.

        Args:
            text: Input text

        Returns:
            Preprocessed text
        """
        if not text or not isinstance(text, str):
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove special characters and numbers
        text = re.sub(r'[^a-zA-Z\s]', '', text)

        # Remove extra whitespace
        text = ' '.join(text.split())

        # Apply NLP preprocessing if available
        if self.nltk_available and self.stop_words and self.lemmatizer:
            try:
                # Tokenize
                tokens = word_tokenize(text)

                # Remove stopwords and short words
                tokens = [word for word in tokens if word not in self.stop_words and len(word) > 2]

                # Lemmatize
                tokens = [self.lemmatizer.lemmatize(word) for word in tokens]

                # Rejoin
                text = ' '.join(tokens)
            except Exception as e:
                logger.warning(f"Error in NLP preprocessing: {e}")

        return text

    def extract_keywords(self, texts: List[str], top_n: int = 10) -> List[str]:
        """
        Extract top keywords from a list of texts.

        Args:
            texts: List of text strings
            top_n: Number of top keywords to extract

        Returns:
            List of top keywords
        """
        if not texts:
            return []

        # Simple word frequency approach (works without sklearn)
        word_freq = {}
        for text in texts:
            if not text:
                continue

            # Preprocess text
            processed_text = self.preprocess_text(text)

            # Count word frequencies
            words = processed_text.split()
            for word in words:
                if len(word) > 2:  # Only count words longer than 2 characters
                    word_freq[word] = word_freq.get(word, 0) + 1

        # Sort by frequency and get top N
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        top_keywords = [word for word, freq in sorted_words[:top_n]]

        return top_keywords

    def analyze_video_titles(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze video titles for common topics and patterns.

        Args:
            df: DataFrame with video data (must have 'Title' column)

        Returns:
            Dictionary with analysis results
        """
        if df.empty or 'Title' not in df.columns:
            return {"error": "No title data available"}

        titles = df['Title'].fillna('').tolist()

        # Extract keywords from titles
        title_keywords = self.extract_keywords(titles, top_n=15)

        # Simple pattern detection in titles
        patterns = self._detect_title_patterns(titles)

        # Calculate title length statistics
        title_lengths = [len(str(title)) for title in titles]

        return {
            "total_videos": len(titles),
            "title_keywords": title_keywords,
            "title_patterns": patterns,
            "avg_title_length": np.mean(title_lengths) if title_lengths else 0,
            "min_title_length": min(title_lengths) if title_lengths else 0,
            "max_title_length": max(title_lengths) if title_lengths else 0,
            "title_length_std": np.std(title_lengths) if title_lengths else 0
        }

    def _detect_title_patterns(self, titles: List[str]) -> Dict[str, List[str]]:
        """
        Detect common patterns in video titles.

        Args:
            titles: List of video titles

        Returns:
            Dictionary of patterns and matching titles
        """
        patterns = {
            "question_titles": [],
            "numbered_titles": [],
            "how_to_titles": [],
            "review_titles": [],
            "tutorial_titles": []
        }

        for title in titles:
            title_lower = str(title).lower()

            # Question titles (end with ? or start with question words)
            if title_lower.endswith('?') or any(title_lower.startswith(q) for q in ['what', 'why', 'how', 'when', 'where', 'who']):
                patterns["question_titles"].append(title)

            # Numbered titles (contain numbers like "10 ways", "5 tips")
            if re.search(r'\d+\s+(ways|tips|tricks|reasons|facts|secrets)', title_lower):
                patterns["numbered_titles"].append(title)

            # How-to titles
            if 'how to' in title_lower or 'tutorial' in title_lower:
                patterns["how_to_titles"].append(title)

            # Review titles
            if any(word in title_lower for word in ['review', 'unboxing', 'test', 'compared']):
                patterns["review_titles"].append(title)

            # Tutorial titles
            if any(word in title_lower for word in ['tutorial', 'guide', 'walkthrough', 'step by step']):
                patterns["tutorial_titles"].append(title)

        # Remove empty pattern lists
        patterns = {k: v for k, v in patterns.items() if v}

        return patterns

    def cluster_content(self, df: pd.DataFrame, num_clusters: int = 5) -> Optional[pd.DataFrame]:
        """
        Cluster videos based on title and description similarity.

        Args:
            df: DataFrame with video data
            num_clusters: Number of clusters to create

        Returns:
            DataFrame with cluster assignments, or None if clustering fails
        """
        if not self.sklearn_available:
            logger.warning("scikit-learn not available for clustering")
            return None

        if df.empty or len(df) < num_clusters:
            logger.warning(f"Not enough data for {num_clusters} clusters")
            return None

        # Prepare text data
        if 'Title' in df.columns and 'Description' in df.columns:
            # Combine title and description for better clustering
            texts = df['Title'].fillna('') + ' ' + df['Description'].fillna('')
        elif 'Title' in df.columns:
            texts = df['Title'].fillna('')
        else:
            logger.warning("No text data available for clustering")
            return None

        # Preprocess texts
        processed_texts = [self.preprocess_text(text) for text in texts]

        # Skip if all texts are empty after preprocessing
        if not any(processed_texts):
            logger.warning("All texts empty after preprocessing")
            return None

        try:
            # Create TF-IDF vectors
            self.vectorizer = TfidfVectorizer(
                max_features=100,
                min_df=2,
                max_df=0.8,
                stop_words='english' if not self.nltk_available else None
            )

            tfidf_matrix = self.vectorizer.fit_transform(processed_texts)

            # Perform clustering
            self.cluster_model = KMeans(
                n_clusters=min(num_clusters, len(df)),
                random_state=42,
                n_init=10
            )

            cluster_labels = self.cluster_model.fit_predict(tfidf_matrix)

            # Get cluster keywords
            cluster_keywords = self._get_cluster_keywords(tfidf_matrix, cluster_labels)

            # Add cluster information to dataframe
            df_result = df.copy()
            df_result['Cluster'] = cluster_labels
            df_result['Cluster_Keywords'] = df_result['Cluster'].map(cluster_keywords)

            # Calculate cluster statistics
            cluster_stats = self._calculate_cluster_stats(df_result)

            logger.info(f"Created {len(set(cluster_labels))} content clusters")
            return df_result

        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            return None

    def _get_cluster_keywords(self, tfidf_matrix, cluster_labels: np.ndarray) -> Dict[int, List[str]]:
        """
        Extract top keywords for each cluster.

        Args:
            tfidf_matrix: TF-IDF feature matrix
            cluster_labels: Cluster assignments

        Returns:
            Dictionary mapping cluster IDs to top keywords
        """
        if self.vectorizer is None:
            return {}

        cluster_keywords = {}
        feature_names = self.vectorizer.get_feature_names_out()

        for cluster_id in set(cluster_labels):
            # Get indices of documents in this cluster
            cluster_indices = np.where(cluster_labels == cluster_id)[0]

            if len(cluster_indices) == 0:
                cluster_keywords[cluster_id] = []
                continue

            # Calculate average TF-IDF scores for this cluster
            cluster_tfidf = tfidf_matrix[cluster_indices].mean(axis=0)
            cluster_tfidf = np.asarray(cluster_tfidf).flatten()

            # Get top 5 keywords for this cluster
            top_indices = cluster_tfidf.argsort()[-5:][::-1]
            keywords = [feature_names[i] for i in top_indices if cluster_tfidf[i] > 0]

            cluster_keywords[cluster_id] = keywords

        return cluster_keywords

    def _calculate_cluster_stats(self, df: pd.DataFrame) -> Dict[int, Dict[str, Any]]:
        """
        Calculate performance statistics for each cluster.

        Args:
            df: DataFrame with cluster assignments and performance metrics

        Returns:
            Dictionary with cluster statistics
        """
        if 'Cluster' not in df.columns:
            return {}

        cluster_stats = {}
        metrics = ['Views', 'Likes', 'Comments', 'Engagement_Rate']

        for cluster_id in sorted(df['Cluster'].unique()):
            cluster_data = df[df['Cluster'] == cluster_id]

            stats = {
                'video_count': len(cluster_data),
                'avg_views': cluster_data['Views'].mean() if 'Views' in cluster_data.columns else 0,
                'avg_likes': cluster_data['Likes'].mean() if 'Likes' in cluster_data.columns else 0,
                'avg_comments': cluster_data['Comments'].mean() if 'Comments' in cluster_data.columns else 0,
                'avg_engagement': cluster_data['Engagement_Rate'].mean() if 'Engagement_Rate' in cluster_data.columns else 0,
                'top_performing_videos': []
            }

            # Get top 3 performing videos in this cluster
            if 'Views' in cluster_data.columns and 'Title' in cluster_data.columns:
                top_videos = cluster_data.nlargest(3, 'Views')[['Title', 'Views']].to_dict('records')
                stats['top_performing_videos'] = top_videos

            cluster_stats[cluster_id] = stats

        return cluster_stats

    def generate_content_insights(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate actionable insights from content analysis.

        Args:
            df: DataFrame with video data and optional cluster assignments

        Returns:
            Dictionary with insights and recommendations
        """
        insights = {
            "title_analysis": {},
            "content_patterns": {},
            "performance_insights": {},
            "recommendations": []
        }

        if df.empty:
            return insights

        # Analyze titles
        insights["title_analysis"] = self.analyze_video_titles(df)

        # Detect content patterns
        titles = df['Title'].fillna('').tolist()
        patterns = self._detect_title_patterns(titles)
        insights["content_patterns"] = patterns

        # Performance insights if metrics available
        if all(col in df.columns for col in ['Views', 'Likes', 'Comments']):
            insights["performance_insights"] = self._analyze_performance_patterns(df)

        # Generate recommendations
        insights["recommendations"] = self._generate_recommendations(insights)

        return insights

    def _analyze_performance_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze performance patterns in the data.

        Args:
            df: DataFrame with performance metrics

        Returns:
            Dictionary with performance insights
        """
        insights = {}

        # Correlation between title length and views
        if 'Title' in df.columns and 'Views' in df.columns:
            title_lengths = df['Title'].apply(lambda x: len(str(x)))
            correlation = title_lengths.corr(df['Views'])
            insights["title_length_correlation"] = correlation

        # Best performing content types
        if 'Content_Type' in df.columns and 'Views' in df.columns:
            type_performance = df.groupby('Content_Type')['Views'].mean().to_dict()
            insights["content_type_performance"] = type_performance

        # Engagement patterns
        if 'Engagement_Rate' in df.columns:
            avg_engagement = df['Engagement_Rate'].mean()
            max_engagement = df['Engagement_Rate'].max()
            min_engagement = df['Engagement_Rate'].min()

            insights["engagement_stats"] = {
                "average": avg_engagement,
                "maximum": max_engagement,
                "minimum": min_engagement,
                "range": max_engagement - min_engagement
            }

        return insights

    def _generate_recommendations(self, insights: Dict[str, Any]) -> List[str]:
        """
        Generate content strategy recommendations.

        Args:
            insights: Dictionary with analysis insights

        Returns:
            List of recommendations
        """
        recommendations = []

        # Title length recommendations
        title_analysis = insights.get("title_analysis", {})
        avg_title_len = title_analysis.get("avg_title_length", 0)

        if avg_title_len < 40:
            recommendations.append("Consider longer titles (40-60 characters) for better SEO")
        elif avg_title_len > 70:
            recommendations.append("Consider shorter titles to avoid truncation in search results")

        # Content pattern recommendations
        patterns = insights.get("content_patterns", {})

        if "question_titles" in patterns and len(patterns["question_titles"]) < 3:
            recommendations.append("Try more question-based titles to attract curious viewers")

        if "how_to_titles" in patterns and len(patterns["how_to_titles"]) < 3:
            recommendations.append("Consider creating more tutorial/how-to content")

        # Performance recommendations
        perf_insights = insights.get("performance_insights", {})

        if "content_type_performance" in perf_insights:
            type_perf = perf_insights["content_type_performance"]
            best_type = max(type_perf.items(), key=lambda x: x[1])[0] if type_perf else None

            if best_type:
                recommendations.append(f"Focus on creating more {best_type} content (highest average views)")

        # Engagement recommendations
        if "engagement_stats" in perf_insights:
            eng_stats = perf_insights["engagement_stats"]
            if eng_stats.get("average", 0) < 5:  # Less than 5% engagement
                recommendations.append("Work on improving engagement through calls-to-action and community interaction")

        return recommendations


# Helper function
def get_content_analyzer() -> ContentAnalyzer:
    """Get a ContentAnalyzer instance."""
    return ContentAnalyzer()


if __name__ == "__main__":
    # Test the content analyzer
    print("Testing ContentAnalyzer...")

    # Create test data
    test_data = {
        'Title': [
            'How to Make Pancakes - Easy Breakfast Recipe',
            '10 Tips for Better Photography',
            'iPhone 15 Review: Is It Worth It?',
            'Python Tutorial for Beginners',
            'My Morning Routine for Productivity',
            'Why I Stopped Using Social Media',
            '5 Secrets to Successful Investing',
            'Car Maintenance Guide for New Owners',
            'What I Eat in a Day - Healthy Meals',
            'Travel Vlog: Japan Adventure'
        ],
        'Views': [1000, 2500, 5000, 3000, 1500, 4000, 2000, 1200, 1800, 3500],
        'Likes': [100, 250, 500, 300, 150, 400, 200, 120, 180, 350],
        'Comments': [20, 50, 100, 60, 30, 80, 40, 24, 36, 70]
    }

    test_df = pd.DataFrame(test_data)
    test_df['Engagement_Rate'] = (test_df['Likes'] / test_df['Views'] * 100).round(2)

    # Create analyzer
    analyzer = ContentAnalyzer()

    # Test title analysis
    print("\n1. Title Analysis:")
    title_analysis = analyzer.analyze_video_titles(test_df)
    print(f"   Keywords: {title_analysis.get('title_keywords', [])[:5]}")
    print(f"   Avg title length: {title_analysis.get('avg_title_length', 0):.1f} chars")

    # Test insights
    print("\n2. Content Insights:")
    insights = analyzer.generate_content_insights(test_df)
    print(f"   Found {len(insights.get('content_patterns', {}))} content patterns")

    recommendations = insights.get('recommendations', [])
    print(f"   Generated {len(recommendations)} recommendations:")
    for i, rec in enumerate(recommendations[:3], 1):
        print(f"     {i}. {rec}")

    # Test clustering if sklearn available
    if SKLEARN_AVAILABLE:
        print("\n3. Content Clustering:")
        clustered_df = analyzer.cluster_content(test_df, num_clusters=3)
        if clustered_df is not None and 'Cluster' in clustered_df.columns:
            print(f"   Created {clustered_df['Cluster'].nunique()} clusters")
            for cluster_id in sorted(clustered_df['Cluster'].unique()):
                cluster_data = clustered_df[clustered_df['Cluster'] == cluster_id]
                keywords = cluster_data['Cluster_Keywords'].iloc[0] if 'Cluster_Keywords' in cluster_data.columns else []
                print(f"   Cluster {cluster_id}: {len(cluster_data)} videos, Keywords: {keywords}")

    print("\nContentAnalyzer test completed!")