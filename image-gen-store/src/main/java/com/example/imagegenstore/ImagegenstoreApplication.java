package com.example.imagegenstore;

import org.springframework.ai.image.ImageModel;
import org.springframework.ai.image.ImagePrompt;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

@RestController
@SpringBootApplication
public class ImagegenstoreApplication {

	private final ImageModel imageModel;
	private final RestClient restClient;

	public ImagegenstoreApplication(ImageModel imageModel, RestClient restClient) {
		this.imageModel = imageModel;
		this.restClient = restClient;
	}

	@PostMapping("/prompt")
	public ResponseEntity<Void> generateImage(@RequestParam String prompt) {
		var response = imageModel.call(new ImagePrompt(prompt));
		var url = response.getResult().getOutput().getUrl();
		
		var bodilessEntity = restClient.post()
				.uri(uriBuilder -> uriBuilder.queryParam("prompt", prompt).queryParam("url", url).build())
				.retrieve()
				.toBodilessEntity();
				
		return ResponseEntity.status(bodilessEntity.getStatusCode()).build();
	}

	public static void main(String[] args) {
		SpringApplication.run(ImagegenstoreApplication.class, args);
	}

	@Bean
	RestClient restClient(RestClient.Builder builder,
						  @Value("${DB_SERVICE_URL:http://localhost:8080/images}") String dbServiceUrl) {
		return builder
				.baseUrl(dbServiceUrl)
				.build();
	}

// 	@Bean
// 	ApplicationRunner runner (Environment env, RestClient rc, ImageModel imageModel, @Value("${AI_PROMPT}") String prompt  ) {
// 		return args -> {
// //			System.out.println("Environment: " + env.getProperty("spring.ai.openai.api-key"));
// 			System.out.println("Environment: " + env.getProperty("AI_PROMPT"));
// 			System.out.println("Environment: " + env.getProperty("DB_SERVICE_URL"));

// 			var response = imageModel.call(new ImagePrompt(prompt));
// 			var url = response.getResult().getOutput().getUrl();
// 			System.out.println("URL: " + url);

// 			var bodilessEntity = rc.post()
// 					.uri( uriBuilder -> uriBuilder  .queryParam("prompt", prompt).queryParam("url", url).build())
// 					.retrieve().toBodilessEntity();
// 			Assert.state(bodilessEntity.getStatusCode().is2xxSuccessful(), "Failed to post to database");
// 		};
// 	}


}

// 1. take in a prompt
// 2. call OpenAI to get image/url
// 3. "post" to curl -XPOST -dprompt="cute raccoon"  -durl="https://i.imgur.com/FLRxq2L.png"  http://localhost:8080/images