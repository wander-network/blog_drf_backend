# Create your views here.
from django.core.cache import cache
from .tasks import send_comment_notification_email
from rest_framework import generics, viewsets, status
from rest_framework_extensions.cache.decorators import cache_response
from rest_framework_extensions.cache.mixins import CacheResponseMixin
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Post, Category, Tag, Comment, LikeRecord
from .serializers import (
    PostListSerializer, PostDetailSerializer, PostCreateSerializer,
    CategorySerializer, TagSerializer, CommentSerializer
)
from .permissions import IsAuthorOrReadOnly
from django.db.models import Q


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.filter(is_published=True)
    permission_classes = [IsAuthorOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'tags']
    search_fields = ['title', 'content', 'summary']
    ordering_fields = ['created_at', 'views', 'likes']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return PostListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PostCreateSerializer
        return PostDetailSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            # 作者本人可以看到自己的所有文章（包括未发布的）
            return Post.objects.filter(
                Q(is_published=True) | Q(author=user)
            )
        # 未登录用户只能看到已发布的文章
        return Post.objects.filter(is_published=True)

    @cache_response(timeout=60 * 30, key_func='retrieve_cache_key')
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        # 更新后清除该文章的缓存
        cache.delete(f'post_detail_{kwargs.get("pk")}')
        return response

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        # 部分更新后也清除缓存
        cache.delete(f'post_detail_{kwargs.get("pk")}')
        return response

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        post = self.get_object()
        like, created = LikeRecord.objects.get_or_create(user=request.user, post=post)
        if created:
            post.likes += 1
            post.save()
            return Response({'likes': post.likes, 'is_liked': True})
        else:
            like.delete()
            post.likes -= 1
            post.save()
            return Response({'likes': post.likes, 'is_liked': False})

    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        post = self.get_object()
        comments = post.comments.all()
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)


class CategoryViewSet(CacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        # 支持查询参数 ?id=1
        category_id = self.request.query_params.get('id')
        if category_id:
            queryset = queryset.filter(id=category_id)
        return queryset

class TagViewSet(CacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        # 支持查询参数 ?id=1
        tag_id = self.request.query_params.get('id')
        if tag_id:
            queryset = queryset.filter(id=tag_id)
        return queryset


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        # 在评论创建成功后，异步发送邮件通知文章作者
        article = comment.post
        author_email = article.author.email
        author_email = comment.post.author.email

        if author_email:  # 确保作者有邮箱地址
            send_comment_notification_email.delay(

                article_title=article.title,
                recipient_email=author_email,
                comment_content=comment.content
            )
            print(f"邮件已发送到 {author_email}")