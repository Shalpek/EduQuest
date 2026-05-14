import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config.dart';

class ApiService {
  static String get baseUrl => AppConfig.baseUrl;

  static Future<Map<String, String>> _getHeaders() async {
    final prefs = await SharedPreferences.getInstance();
    final authToken = prefs.getString('auth_token');
    return {
      'Content-Type': 'application/json',
      if (authToken != null && authToken.isNotEmpty)
        'Authorization': 'Bearer $authToken',
    };
  }

  static Future<Map<String, dynamic>?> login(
    String email,
    String password,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email, 'password': password}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('auth_token', data['token'] ?? '');
        await prefs.setInt('user_id', data['user_id']);
        await prefs.setString('user_email', data['email'] ?? email);
        await prefs.setString('user_name', data['full_name'] ?? '');
        await prefs.setString('user_role', data['role'] ?? 'student');
        return data;
      }
      return null;
    } catch (e) {
      debugPrint('Login error: $e');
      return null;
    }
  }

  static Future<Map<String, dynamic>?> register(
    String fullName,
    String email,
    String password,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'full_name': fullName,
          'email': email,
          'password': password,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (e) {
      debugPrint('Register error: $e');
    }
    return null;
  }

  static Future<Map<String, dynamic>?> getCurrentUser() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/auth/me'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('user_email', data['email'] ?? '');
        await prefs.setString('user_name', data['full_name'] ?? '');
        await prefs.setString('user_role', data['role'] ?? 'student');
        return data;
      }
    } catch (_) {}
    return null;
  }

  static Future<bool> updateCurrentUser(String fullName) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/auth/me'),
        headers: await _getHeaders(),
        body: jsonEncode({'full_name': fullName}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('user_name', data['full_name'] ?? fullName);
        return true;
      }
    } catch (_) {}
    return false;
  }

  static Future<String?> changePassword(
    String currentPassword,
    String newPassword,
  ) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/auth/change-password'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'current_password': currentPassword,
          'new_password': newPassword,
        }),
      );
      if (response.statusCode == 200) return null;
      final data = jsonDecode(response.body);
      return data['detail']?.toString() ?? 'Unable to update password';
    } catch (_) {
      return 'Unable to update password';
    }
  }

  static Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    await prefs.remove('user_id');
    await prefs.remove('user_email');
    await prefs.remove('user_name');
    await prefs.remove('user_role');
  }

  static Future<Map<String, dynamic>?> getProfile(int userId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/gamification/profile/$userId'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<bool> completeLesson(int userId, int lessonId) async {
    try {
      final response = await http.post(
        Uri.parse(
          '$baseUrl/gamification/profile/$userId/complete_lesson/$lessonId',
        ),
        headers: await _getHeaders(),
      );
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<List<dynamic>> getUserAttempts(int userId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/quizzes/user/$userId/attempts'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<List<dynamic>> getCourses() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/courses/'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<List<dynamic>> getLessons(int courseId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/courses/$courseId/lessons'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<Map<String, dynamic>?> getCourseContentMap(int courseId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/courses/$courseId/content-map'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> getQuiz(int lessonId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/quizzes/lesson/$lessonId'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> submitQuiz(
    int quizId,
    List<int> answers,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/quizzes/$quizId/submit'),
        headers: await _getHeaders(),
        body: jsonEncode({'answers': answers}),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<String> getAiHint(int userId, String question) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/hint'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'user_id': userId,
          'context': 'General',
          'user_question': question,
        }),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['hint'];
      }
      return "I'm having trouble connecting to my knowledge base right now.";
    } catch (e) {
      return "Network error: Unable to reach AI Tutor.";
    }
  }

  static Future<Map<String, dynamic>?> getAiMistakeReview(
    int userId,
    String lessonTitle,
    List<Map<String, dynamic>> wrongAnswers,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/review-mistakes'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'user_id': userId,
          'lesson_title': lessonTitle,
          'wrong_answers': wrongAnswers,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<String> askAiReviewFollowUp(
    int userId,
    String lessonTitle,
    List<Map<String, dynamic>> wrongAnswers,
    String userQuestion,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/review-chat'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'user_id': userId,
          'lesson_title': lessonTitle,
          'wrong_answers': wrongAnswers,
          'user_question': userQuestion,
        }),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['answer']?.toString() ??
            'I could not generate an explanation.';
      }
    } catch (_) {}
    return 'I could not generate an explanation right now. Please try again.';
  }

  static Future<Map<String, dynamic>?> getTeacherDashboard() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/dashboard'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<List<dynamic>> getStudentsProgress() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/students-progress'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<List<dynamic>> getTeacherAttempts() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/recent-attempts'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<Map<String, dynamic>?> getTeacherAnalyticsSummary() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/analytics-summary'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<List<dynamic>> getTeacherAssignments() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/assignments'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<Map<String, dynamic>?> createTeacherAssignment({
    required int quizId,
    required int courseId,
    required String title,
    required String instructions,
    String? dueAt,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/assignments'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'quiz_id': quizId,
          'course_id': courseId,
          'title': title,
          'instructions': instructions,
          'due_at': dueAt,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> updateTeacherAssignment({
    required int assignmentId,
    required int quizId,
    required int courseId,
    required String title,
    required String instructions,
    String? dueAt,
  }) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/teacher/assignments/$assignmentId'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'quiz_id': quizId,
          'course_id': courseId,
          'title': title,
          'instructions': instructions,
          'due_at': dueAt,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> publishTeacherAssignment(
    int assignmentId,
  ) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/teacher/assignments/$assignmentId/publish'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  // Teacher Content Management
  static Future<Map<String, dynamic>?> createCourse(
    String title,
    String description,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/courses'),
        headers: await _getHeaders(),
        body: jsonEncode({'title': title, 'description': description}),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> createLesson(
    int courseId,
    String title,
    String content,
    int order,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/lessons'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'course_id': courseId,
          'title': title,
          'content': content,
          'order': order,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> createQuiz(
    int lessonId,
    String title,
    List<dynamic> questions,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/quizzes'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'lesson_id': lessonId,
          'title': title,
          'questions': questions,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<List<dynamic>> getUsers() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/admin/users'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<bool> toggleUserStatus(int userId, bool active) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/admin/users/$userId/status?active=$active'),
        headers: await _getHeaders(),
      );
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<bool> changeUserRole(int userId, String role) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/admin/users/$userId/role?role=$role'),
        headers: await _getHeaders(),
      );
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<Map<String, dynamic>?> getSystemConfig() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/admin/config'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> getAppConfig() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/app/config'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<bool> updateSystemConfig(
    bool aiSafety,
    bool retries,
    int xp,
  ) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/admin/config'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'ai_safety': aiSafety,
          'retries_enabled': retries,
          'xp_per_quiz': xp,
        }),
      );
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<Map<String, dynamic>?> getPlatformStatus() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/admin/platform-status'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> getAnalyticsOverview() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/analytics/overview'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }
}
