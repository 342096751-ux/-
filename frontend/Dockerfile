FROM nginx:alpine

# 拷贝前端静态资源
COPY dist /usr/share/nginx/html

# 覆盖默认 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
